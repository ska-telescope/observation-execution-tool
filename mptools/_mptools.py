# -*- coding: utf-8 -*-

"""Main module."""

import functools
import logging
import logging.config
import logging.handlers
import multiprocessing as mp
import multiprocessing.queues as mpq
import multiprocessing.synchronize as mps
import signal
import sys
import time
from queue import Empty, Full
from typing import Any, List, Tuple, Type, Union

MPQUEUE_TIMEOUT = 0.02


# -- Queue handling support

class MPQueue(mpq.Queue):
    """
    MPQueue is a multiprocessing Queue extended with convenience methods that
    return booleans to reflect success and failure rather than raising
    exceptions.

    MPQueue adds methods to:
      - get next item in an exception-free manner
      - put an item in an exception-free manner
      - drain queue to allow safe closure
      - close queue in an exception-free manner
    """

    # -- See StackOverflow Article :
    #   https://stackoverflow.com/questions/39496554/cannot-subclass-multiprocessing-queue-in-python-3-5
    #
    # -- tldr; mp.Queue is a _method_ that returns an mpq.Queue object.  That object
    # requires a context for proper operation, so this __init__ does that work as well.
    def __init__(self, maxsize=0):
        ctx = mp.get_context()
        super().__init__(maxsize, ctx=ctx)

    def safe_get(self, timeout: Union[float, None] = MPQUEUE_TIMEOUT):
        try:
            if timeout is None:
                return self.get(block=False)
            else:
                return self.get(block=True, timeout=timeout)
        except Empty:
            return None

    def safe_put(self, item, timeout: Union[float, None] = MPQUEUE_TIMEOUT) -> bool:
        try:
            self.put(item, block=False, timeout=timeout)
            return True
        except Full:
            return False

    def drain(self):
        item = self.safe_get()
        while item:
            yield item
            item = self.safe_get()

    def safe_close(self) -> int:
        num_left = sum(1 for _ in self.drain())
        self.close()
        self.join_thread()
        return num_left


# -- useful function
def _sleep_secs(max_sleep, end_time=sys.float_info.max):
    # Calculate time left to sleep, no less than 0
    return max(0.0, min(end_time - time.time(), max_sleep))


# -- Standard Event Queue manager
class EventMessage:
    def __init__(self, msg_src: str, msg_type: str, msg: Any):
        self.id = time.time()
        self.msg_src = msg_src
        self.msg_type = msg_type
        self.msg = msg

    def __str__(self):
        return f"{self.msg_src:10} - {self.msg_type:10} : {self.msg}"


# -- Signal Handling
class TerminateInterrupt(BaseException):
    pass


class SignalObject:
    MAX_TERMINATE_CALLED = 3

    def __init__(self, shutdown_event: mps.Event):
        self.terminate_called = 0
        self.shutdown_event = shutdown_event


def default_signal_handler(signal_object: SignalObject, exception_class, signal_num: int, current_stack_frame):
    signal_object.terminate_called += 1
    signal_object.shutdown_event.set()
    if signal_object.terminate_called >= signal_object.MAX_TERMINATE_CALLED:
        raise exception_class()


def init_signal(signal_num, signal_object: SignalObject, exception_class, handler):
    handler = functools.partial(handler, signal_object, exception_class)
    signal.signal(signal_num, handler)
    signal.siginterrupt(signal_num, False)


def init_signals(shutdown_event, int_handler, term_handler):
    signal_object = SignalObject(shutdown_event)
    init_signal(signal.SIGINT, signal_object, KeyboardInterrupt, int_handler)
    init_signal(signal.SIGTERM, signal_object, TerminateInterrupt, term_handler)
    return signal_object


# -- Worker Process classes

class ProcWorker:
    # Number of times terminate is retried before
    MAX_TERMINATE_CALLED = 3

    # signal handler for SIGINT
    int_handler = staticmethod(default_signal_handler)
    # signal handler for SIGTERM
    term_handler = staticmethod(default_signal_handler)

    def __init__(self,
                 name: str,
                 startup_event: mps.Event,
                 shutdown_event: mps.Event,
                 event_q: MPQueue,
                 *args,
                 logging_config: dict = None):
        """
        ProcWorker is a template class for code that should operate in a child
        process.

        ProcWorker

        :param name: name of this worker
        :param startup_event: event to set on startup completion
        :param shutdown_event: event to monitor for shutdown
        :param event_q: queue for messages to/from MainWorker
        :param args:
        """
        self.name = name
        self.log = functools.partial(logging.log, extra=dict(source=f'{self.name} Worker'))
        self.startup_event = startup_event
        self.shutdown_event = shutdown_event
        self.event_q = event_q
        self.terminate_called = 0
        self.init_args(args)
        self.logging_config = logging_config

    def init_logging(self):
        self.log(logging.DEBUG, "Entering init_logging")
        if self.logging_config:
            logging.config.dictConfig(self.logging_config)

    def init_args(self, args) -> None:
        if args:
            raise ValueError(f"Unexpected arguments to ProcWorker.init_args: {args}")

    def init_signals(self) -> SignalObject:
        """
        Initialise the signal handler
        :return:
        """
        self.log(logging.DEBUG, "Entering init_signals")
        signal_object = init_signals(self.shutdown_event, self.int_handler, self.term_handler)
        return signal_object

    def main_loop(self) -> None:
        """
        main_loop is called
        :return:
        """
        self.log(logging.DEBUG, "Entering main_loop")
        while not self.shutdown_event.is_set():
            self.main_func()

    def startup(self) -> None:
        self.log(logging.DEBUG, "Entering startup")

    def shutdown(self) -> None:
        self.log(logging.DEBUG, "Entering shutdown")

    def main_func(self, *args):
        self.log(logging.DEBUG, "Entering main_func")
        raise NotImplementedError(f"{self.__class__.__name__}.main_func is not implemented")

    def run(self) -> int:
        """
        Start ProcWorker execution.

        This method performs the housekeeping required to set the worker
        instance running and starts the main loop. An exit code of 0 is
        returned if the main loop completes and exits cleanly.

        :return: exit status code
        """
        self.init_signals()

        try:
            self.init_logging()

            self.startup()
            self.startup_event.set()

            # Start main loop execution
            self.main_loop()

            # A well behaved main_loop exits when the shutdown event is set or
            # the END sentinel message is received. When this occurs, control
            # flow moves here and we broadcast that a normal shutdown occurred.
            self.log(logging.INFO, "Normal Shutdown")
            self.event_q.safe_put(EventMessage(self.name, "SHUTDOWN", "Normal"))
            return 0

        except BaseException as exc:
            # We get here if an exception was raised in the main_loop.

            # -- Catch ALL exceptions, even Terminate and Keyboard interrupt
            self.log(logging.ERROR, f"Exception Shutdown: {exc}", exc_info=True)
            self.event_q.safe_put(EventMessage(self.name, "FATAL", f"{exc}"))
            # -- TODO: call raise if in some sort of interactive mode
            if type(exc) in (TerminateInterrupt, KeyboardInterrupt):
                sys.exit(1)
            else:
                sys.exit(2)

        finally:
            self.shutdown()


class TimerProcWorker(ProcWorker):
    """
    TimerProcWorker is a ProcWorker that calls main_func on a fixed cadence.
    """
    # Interval between calls to main_func()
    INTERVAL_SECS = 10

    # Interval for checking shutdown event status
    SHUTDOWN_CHECK_INTERVAL = 0.02

    def main_loop(self):
        self.log(logging.DEBUG, "Entering TimerProcWorker.main_loop")
        next_time = time.time() + self.INTERVAL_SECS
        while not self.shutdown_event.is_set():
            sleep_secs = _sleep_secs(self.SHUTDOWN_CHECK_INTERVAL, next_time)
            time.sleep(sleep_secs)
            if time.time() > next_time:
                self.log(logging.DEBUG, "TimerProcWorker.main_loop : calling main_func")
                self.main_func()
                next_time = time.time() + self.INTERVAL_SECS


class QueueProcWorker(ProcWorker):
    """
    QueueProcWorker is a ProcWorker that calls main_func with every item
    received on a work queue.
    """

    def __init__(self,
                 name: str,
                 startup_event: mps.Event,
                 shutdown_event: mps.Event,
                 event_q: MPQueue,
                 work_q: MPQueue,
                 *args,
                 **kwargs):
        super().__init__(name, startup_event, shutdown_event, event_q, *args, **kwargs)
        # work_q.owner = name
        self.work_q = work_q

    def main_loop(self):
        self.log(logging.DEBUG, "Entering QueueProcWorker.main_loop")

        while not self.shutdown_event.is_set():
            # Get next work item. This call will return after the default
            # safe_get timeout unless an item is in the queue.
            item = self.work_q.safe_get()

            # No item received within timeout period
            if not item:
                continue

            # item received from queue
            self.log(logging.DEBUG, f"QueueProcWorker.main_loop received '{item}' message")
            if item == "END":
                # Sentinel message - end main loop
                break
            else:
                # otherwise call main function with the queue item
                self.main_func(item)


# -- Process Wrapper

def proc_worker_wrapper(proc_worker_class: Type[ProcWorker],
                        name: str,
                        startup_evt: mps.Event,
                        shutdown_evt: mps.Event,
                        event_q: MPQueue,
                        *args,
                        **kwargs):
    """
    This function is called to launch the worker task from within the child
    process.

    :param proc_worker_class: worker class to instantiate
    :param name: name for this ProcWorker
    :param startup_evt: start-up event to share with worker
    :param shutdown_evt: shutdown event to share with worker
    :param event_q: event queue to share with worker
    :param args: any additional arguments to give to worker constructor
    :return:
    """
    proc_worker = proc_worker_class(name, startup_evt, shutdown_evt, event_q, *args, **kwargs)
    return proc_worker.run()


class Proc:
    """
    Proc represents a child process of a MainContext.

    Proc arranges for a ProcWorker to execute in a new child process. Proc is
    responsible for managing the lifecycle of the child process.
    """
    # Start-up grace time before giving up and terminating the ProcWorker
    STARTUP_WAIT_SECS = 3.0
    # Grace time from setting shutdown event to Shutdown grace time before terminating
    SHUTDOWN_WAIT_SECS = 3.0

    def __init__(self,
                 name: str,
                 worker_class: Type[ProcWorker],
                 shutdown_event: mps.Event,
                 event_q: MPQueue,
                 *args,
                 logging_config: dict = None):
        # Prefix log messages originating from this process with the process name
        if logging_config:
            logging.config.dictConfig(logging_config)
        self.log = functools.partial(logging.log, extra=dict(source=f'{name} Worker'))

        self.name = name

        # Store the shutdown event which is shared with the MainContext and all other Procs
        self.shutdown_event = shutdown_event
        # But this proc provides the context for the startup event, set by the
        # ProcWorker to indicate that startup is complete.
        self.startup_event = mp.Event()

        # Arrange for the ProcWorker constructor helper function to
        self.proc = mp.Process(
            target=proc_worker_wrapper,
            name=name,
            args=(worker_class, name, self.startup_event, shutdown_event, event_q, *args),
            kwargs=dict(logging_config=logging_config)
        )
        self.log(logging.DEBUG, f"Proc.__init__ starting : {name}")
        self.proc.start()
        started = self.startup_event.wait(timeout=Proc.STARTUP_WAIT_SECS)
        self.log(logging.DEBUG, f"Proc.__init__ starting : {name} got {started}")
        if not started:
            self.terminate()
            raise RuntimeError(f"Process {name} failed to startup after {Proc.STARTUP_WAIT_SECS} seconds")

    def full_stop(self, wait_time=SHUTDOWN_WAIT_SECS) -> None:
        """
        Stop the ProcWorker child process.

        The method will attempt to terminate ProcWorker execution, first by
        setting the shutdown event and giving the ProcWorker opportunity to
        cleanly exit. If the ProcWorker has not terminated after wait_time
        seconds, SIGTERM signals are sent to the child process hosting the
        ProcWorker.

        :param wait_time: grace time before sending SIGTERM signals
        """
        self.log(logging.DEBUG, f"Proc.full_stop stopping : {self.name}")
        self.shutdown_event.set()
        self.proc.join(wait_time)
        if self.proc.is_alive():
            self.terminate()

    def terminate(self, max_retries=3, timeout=0.1) -> bool:
        """
        Terminate the child process using POSIX signals.

        This function sends SIGTERM to the child process, waiting timeout
        seconds before checking process status and, if the process is still
        alive, trying again.

        :param max_retries: max retry attempts
        :param timeout: second to wait before retry
        :return: True if process termination was successful
        """
        self.log(logging.DEBUG, f"Proc.terminate terminating : {self.name}")
        attempt = 0
        while self.proc.is_alive():
            self.proc.terminate()
            self.proc.join(timeout)
            attempt += 1
            if attempt >= max_retries:
                break

        if self.proc.is_alive():
            self.log(logging.ERROR, f"Proc.terminate failed to terminate {self.name} after {attempt} attempts")
            return False
        else:
            self.log(logging.INFO, f"Proc.terminate terminated {self.name} after {max_retries - attempt} attempt(s)")
            return True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.full_stop()
        return not exc_type


# -- Main Wrappers
class MainContext:
    """
    MainContext is the parent context for a set of worker processes that
    communicate via message queues.
    """

    # Grace period after setting shutdown_event before processes are forcibly terminated
    STOP_WAIT_SECS = 3.0

    def __init__(self):
        self.procs: List[Proc] = []
        self.queues: List[MPQueue] = []
        self.log = functools.partial(logging.log, extra=dict(source='MAIN'))

        # Event that is set to signify shutdown has been requested
        self.shutdown_event = mp.Event()

        # main event queue receiving messages to be routed/acted upon
        self.event_queue = self.MPQueue()

        # # queue for log messages
        self.logging_config = None

    def init_logging(self, config):
        self.logging_config = config
        logging.config.dictConfig(config)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.log(logging.ERROR, f"Exception: {exc_val}", exc_info=(exc_type, exc_val, exc_tb))

        self._stopped_procs_result = self.stop_procs()
        self._stopped_queues_result = self.stop_queues()

        # -- Don't eat exceptions that reach here.
        return not exc_type

    def Proc(self, name: str, worker_class: Type[ProcWorker], *args) -> Proc:
        """
        Create a new process managed by this context.

        :param name: name for worker process
        :param worker_class: worker process class
        :param args: argument to pass to worker constructor
        :return: worker instance
        """
        proc = Proc(name, worker_class, self.shutdown_event, self.event_queue, *args,
                    logging_config=self.logging_config)
        self.procs.append(proc)
        return proc

    def MPQueue(self, *args, **kwargs) -> MPQueue:
        """
        Create a new message queue managed by this context.

        :param args: queue constructor args
        :param kwargs: queue constructor kwargs
        :return: message queue instance
        """
        q = MPQueue(*args, **kwargs)
        self.queues.append(q)
        return q

    def stop_procs(self) -> Tuple[int, int]:
        # Post END sentinel message and set shutdown event
        self.event_queue.safe_put(EventMessage("stop_procs", "END", "END"))
        self.shutdown_event.set()

        # Wait up to STOP_WAIT_SECS for all processes to complete
        end_time = time.time() + self.STOP_WAIT_SECS
        for proc in self.procs:
            join_secs = _sleep_secs(self.STOP_WAIT_SECS, end_time)
            proc.proc.join(join_secs)

        # -- Clear the procs list and _terminate_ any procs that
        # have not yet exited
        num_terminated = 0
        num_failed = 0
        still_running = []
        while self.procs:
            proc = self.procs.pop()
            if proc.proc.is_alive():
                if proc.terminate():
                    num_terminated += 1
                else:
                    still_running.append(proc)
            else:
                exitcode = proc.proc.exitcode
                if exitcode:
                    self.log(logging.ERROR, f"Process {proc.name} ended with exitcode {exitcode}")
                    num_failed += 1
                else:
                    self.log(logging.DEBUG, f"Process {proc.name} stopped successfully")

        self.procs = still_running

        return num_failed, num_terminated

    def stop_queues(self) -> int:
        """
        Drain all queues, blocking until they have stopped.

        :return: number of items drained
        """
        num_items_left = 0

        # Clear the queues list and close all associated queues
        for q in self.queues:
            num_items_left += sum(1 for __ in q.drain())
            q.close()

        # Wait for all queue threads to stop
        while self.queues:
            q = self.queues.pop(0)
            q.join_thread()

        return num_items_left
