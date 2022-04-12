# -*- coding: utf-8 -*-

"""Main module for MPTools.

This module is largely based on Pamela McA'Nulty's MPTools project and is
subject to the following licence.

MIT License

Copyright (c) 2019, Pamela D McA'Nulty

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""
import functools
import logging
import logging.config
import logging.handlers
import multiprocessing as mp
import multiprocessing.queues as mpq
import multiprocessing.synchronize as mps
import signal
import sys
import threading
import time
import traceback
from queue import Empty, Full
from types import FrameType
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
        """
        Remove and return an item from this MPQueue.

        If optional arg timeout is None, safe_get returns an item if one is
        immediately available. If optional arg timeout is a positive number
        (the default), safe_get blocks at most timeout seconds for an item to
        become available. In either case, None is returned if no item is
        available.

        :param timeout: maximum timeout in seconds, or None for no waiting
           period
        :return: None if no item is available
        """
        try:
            if timeout is None:
                return self.get(block=False)
            return self.get(block=True, timeout=timeout)
        except Empty:
            return None

    def safe_put(self, item, timeout: Union[float, None] = MPQUEUE_TIMEOUT) -> bool:
        """
        Put an item on this MPQueue.

        safe_put adds an item onto the queue if a free slot is available,
        blocking at most timeout seconds for a free slot and returning False
        if no free slot was available within that time.

        :param item: item to add
        :param timeout: timeout in seconds
        :return: True if the operation succeeded within the timeout
        """
        try:
            self.put(item, block=False, timeout=timeout)
            return True
        except Full:
            return False

    def drain(self):
        """
        Drain all items from this MPQueue, yielding each item until all items
        have been removed.
        """
        item = self.safe_get()
        while item:
            yield item
            item = self.safe_get()

    def safe_close(self) -> int:
        """
        Drain and close this MPQueue.

        No more items can be added to this MPQueue one safe_close has been
        called.
        """
        num_left = sum(1 for _ in self.drain())
        self.close()
        self.join_thread()
        return num_left


# -- useful function
def _sleep_secs(max_sleep, end_time=sys.float_info.max):
    # Calculate time left to sleep, no less than 0
    return max(0.0, min(end_time - time.time(), max_sleep))


class EventMessage:
    """
    EventMessage holds the message and message metadata for events sent on the
    event queue between MPTools ProcWorkers.
    """

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
    """
    SignalObject is a struct holding properties and state referenced by
    mptools signal handlers during their processing.

    Setting the SignalObject.shutdown_event will request all MPTools processes
    cooperatively shut down. SignalObject also records how many times a signal
    has been received, allowing escalation for processes that do not
    co-operate with shutdown_event requests.
    """

    # Number of times terminate can be retried before hard kill
    MAX_TERMINATE_CALLED = 3

    def __init__(self, shutdown_event: mps.Event):
        """
        Create a new SignalObject.

        :param shutdown_event: shutdown Event shared between all MPTools
            processes
        """
        self.terminate_called = 0
        self.shutdown_event = shutdown_event


def default_signal_handler(
    signal_object: SignalObject,
    exception_class,
    signal_num: int,  # pylint: disable=unused-argument
    current_stack_frame: Union[FrameType, None],  # pylint: disable=unused-argument
) -> None:
    """
    Custom signal handling function that requests co-operative ProcWorker
    shutdown by setting the shared Event, forcibly terminating the process by
    raising an instance of the given exception class if call limit has been
    exceeded.

    :param signal_object: SignalObject to modify to reflect signal-handling
        state
    :param exception_class: Exception type to raise when call limit is
        exceeded
    :param signal_num: POSIX signal ID
    :param current_stack_frame: current stack frame
    """
    signal_object.terminate_called += 1
    signal_object.shutdown_event.set()
    if signal_object.terminate_called >= signal_object.MAX_TERMINATE_CALLED:
        raise exception_class()


def init_signal(signal_num: Any, signal_object: SignalObject, exception_class, handler):
    # Pass each signal handler the SignalObject and exception class when called
    handler = functools.partial(handler, signal_object, exception_class)
    signal.signal(signal_num, handler)
    signal.siginterrupt(signal_num, False)


def init_signals(shutdown_event, int_handler, term_handler) -> SignalObject:
    """
    Install SIGINT and SIGTERM signal handlers for the running Python process.

    This function returns the SignalObject shared with signal handlers that
    the handlers use to store signal handling state.

    :param shutdown_event: Event to set when SIGINT or SIGTERM is received
    :param int_handler: SIGINT handler function to install
    :param term_handler: SIGTERM handler function to install
    :return: SignalObject processed by signal handlers
    """
    signal_object = SignalObject(shutdown_event)
    init_signal(signal.SIGINT, signal_object, KeyboardInterrupt, int_handler)
    init_signal(signal.SIGTERM, signal_object, TerminateInterrupt, term_handler)
    return signal_object


# -- Worker Process classes


class ProcWorker:
    """
    ProcWorker is a template class for code that should execute in a child
    Python interpreter process.

    ProcWorker contains the standard boilerplate code required to set up a
    well-behaved child process. It handles starting the process, connecting
    signal handlers, signalling the parent that startup completed, etc.
    ProcWorker does not contain any business logic, which should be defined
    in a subclass of ProcWorker.

    The core ProcWorker template method is main_loop, which is called once
    startup is complete and main execution begins. In ProcWorker this method
    is left blank and should be overridden by the class extending ProcWorker.
    Once the main_loop method is complete, the ProcWorker is shut down.

    MPTools provides some ProcWorker subclasses with main_loop implementations
    that provide different kinds of behaviour. For instance,

    - TimerProcWorker.main_loop has code calls a function on a fixed cadence;
    - QueueProcWorker.main_loop has code that gets items from a queue, calling
      a function with every item received.
    """

    # set default_signal_handler function as SIGINT and SIGTERM handlers for
    # this class
    int_handler = staticmethod(default_signal_handler)
    term_handler = staticmethod(default_signal_handler)

    def __init__(
        self,
        name: str,
        startup_event: mps.Event,
        shutdown_event: mps.Event,
        event_q: MPQueue,
        *args,
        logging_config: dict = None,
        **kwargs,
    ):
        """
        Create a new ProcWorker.

        :param name: name of this worker
        :param startup_event: event to set on startup completion
        :param shutdown_event: event to monitor for shutdown
        :param event_q: queue for messages to/from MainWorker
        :param args:
        """
        self.name = name
        # setting thread name makes logs easier to understand
        threading.current_thread().name = name

        self.log = functools.partial(
            logging.log, extra=dict(source=f"{self.name} Worker")
        )
        self.startup_event = startup_event
        self.shutdown_event = shutdown_event
        self.event_q = event_q
        self.terminate_called = 0
        self.init_args(args, kwargs)
        self.logging_config = logging_config

    def init_logging(self):
        self.log(logging.DEBUG, "Entering init_logging")
        if self.logging_config:
            logging.config.dictConfig(self.logging_config)

    def init_args(self, args, kwargs) -> None:
        if args:
            raise ValueError(f"Unexpected arguments to ProcWorker.init_args: {args}")
        if kwargs:
            raise ValueError(
                f"Unexpected keyword arguments to ProcWorker.init_args: {kwargs}"
            )

    def init_signals(self) -> SignalObject:
        """
        Initialise signal handlers for this worker process.

        Calling this method will install SIGTERM and SIGINT signal handlers
        for the running process.
        """
        self.log(logging.DEBUG, "Entering init_signals")
        signal_object = init_signals(
            self.shutdown_event, self.int_handler, self.term_handler
        )
        return signal_object

    def main_loop(self) -> None:
        self.log(logging.DEBUG, "Entering main_loop")
        while not self.shutdown_event.is_set():
            self.main_func()

    def startup(self) -> None:
        self.log(logging.DEBUG, "Entering startup")

    def shutdown(self) -> None:
        self.log(logging.DEBUG, "Entering shutdown")

    def main_func(self):
        self.log(logging.DEBUG, "Entering main_func")
        raise NotImplementedError(
            f"{self.__class__.__name__}.main_func is not implemented"
        )

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

            # A well-behaved main_loop exits when the shutdown event is set or
            # the END sentinel message is received. When this occurs, control
            # flow moves here and we broadcast that a normal shutdown occurred.
            self.log(logging.INFO, "Normal Shutdown")
            self.event_q.safe_put(EventMessage(self.name, "SHUTDOWN", "Normal"))
            return 0

        except BaseException as exc:
            # We get here if an exception was raised in the main_loop, even
            # TerminateInterrupt and KeyboardInterrupt
            self.log(logging.ERROR, f"Exception Shutdown: {exc}", exc_info=True)

            # self.event_q.safe_put(EventMessage(self.name, "FATAL", f"{exc}"))
            stacktrace = traceback.format_exc()
            self.event_q.safe_put(EventMessage(self.name, "FATAL", f"{stacktrace}"))
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
    received on its work queue.
    """

    def __init__(
        self,
        name: str,
        startup_event: mps.Event,
        shutdown_event: mps.Event,
        event_q: MPQueue,
        work_q: MPQueue,
        *args,
        **kwargs,
    ):
        """
        Create a new QueueProcWorker.

        The events and MPQueues passed to this constructor should be created
        and managed within the scope of a MainContext context manager and
        shared with other ProcWorkers, so that the communication queues are
        shared correctly between Python processes and there is a common event
        that can be set to notify all processes when shutdown is required.

        :param name: name of this worker
        :param startup_event: event to trigger when startup is complete
        :param shutdown_event: event to monitor for shutdown
        :param event_q: outbox for posting messages to main context
        :param work_q: inbox message queue for work messages
        :param args: captures other anonymous arguments
        :param kwargs: captures other keyword arguments
        """
        super().__init__(name, startup_event, shutdown_event, event_q, *args, **kwargs)
        # work_q.owner = name
        self.work_q = work_q

    def main_loop(self) -> None:
        """
        main_loop delivers each event received on the work queue to the
        main_func template method, while checking for shutdown notifications.

        Event delivery will cease when the shutdown event is set or a special
        sentinel message is sent.
        """
        self.log(logging.DEBUG, "Entering QueueProcWorker.main_loop")

        # stop processing as soon as the shutdown_event is set. Once set, this
        # while loop terminates, thus ending main_loop and starting shutdown
        # of this ProcWorker.
        while not self.shutdown_event.is_set():

            # Get next work item. This call returns after the default safe_get
            # timeout unless an item is in the queue.
            item = self.work_q.safe_get()

            # Go back to the top of the while loop if no message was received,
            # thus checking the shutdown event again.
            if not item:
                continue

            # ok - an item was received from queue
            self.log(
                logging.DEBUG, f"QueueProcWorker.main_loop received '{item}' message"
            )
            # if item is the sentinel message, break to exit out of main_loop
            # and start shutdown
            if item == "END":
                break

            # otherwise call main function with the queue item
            else:
                self.main_func(item)

    # Relax pylint as we are deliberately redefining the superclass main_func
    # signature in this specialised subclass. This is intended to be a
    # template, hence the implementation doesn't use item.
    def main_func(self, item):  # pylint: disable=unused-argument,arguments-differ
        # rely on a call to super to raise NotImplementedError
        super().main_func()


# -- Process Wrapper


def proc_worker_wrapper(
    proc_worker_class: Type[ProcWorker],
    name: str,
    startup_evt: mps.Event,
    shutdown_evt: mps.Event,
    event_q: MPQueue,
    *args,
    **kwargs,
):
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
    proc_worker = proc_worker_class(
        name, startup_evt, shutdown_evt, event_q, *args, **kwargs
    )
    return proc_worker.run()


class Proc:
    """
    Proc represents a child process of a MainContext.

    Proc instances exist in the scope of a MainContext instance and in the
    same Python interpreter process as the MainContext. Procs are the
    MainContext's link to the ProcWorkers which run in separate Python
    interpreters. Every ProcWorker running in a child process is associated
    with one Proc.

    Each Proc is responsible for bootstrapping its ProcWorker and managing its
    lifecycle. Proc arranges for an instance of the ProcWorker class passed as
    a constructor argument to be initialised and start running in a new child
    Python interpreter. Proc checks that the ProcWorker has started
    successfully by checking the status of a multiprocessing Event passed to
    the ProcWorker as a constructor argument, which should be set by the
    ProcWorker on successful startup. If ProcWorker startup does not complete
    successfully and the event is left unset, Proc will forcibly terminate the
    child process and report the error.

    Proc is able to terminate its associated ProcWorker, first by giving the
    ProcWorker chance to co-operatively exit by setting the shutdown event. If
    the ProcWorker does not respond by exiting within the grace period set by
    Proc.SHUTDOWN_WAIT_SECS, Proc will forcibly terminate the ProcWorker's
    process.

    Proc ensures that the shutdown event and MPQueues it receives are passed
    through to the ProcWorker. Note that by default only one shutdown event is
    created by the MainContext, so setting the shutdown event triggers
    shutdown in all ProcWorkers!

    Proc does not contain any business logic or application-specific code,
    which should be contained in the ProcWorker - or more likely, a class that
    extends ProcWorker.
    """

    # Start-up grace time before Proc gives up and terminates the ProcWorker
    STARTUP_WAIT_SECS = 3.0

    # Grace time allowed from Proc setting the shutdown event to Proc forcibly
    # terminating the ProcWorker
    SHUTDOWN_WAIT_SECS = 3.0

    def __init__(
        self,
        name: str,
        worker_class: Type[ProcWorker],
        shutdown_event: mps.Event,
        event_q: MPQueue,
        *args,
        logging_config: dict = None,
        **kwargs,
    ):
        # Prefix log messages originating from this process with the process name
        if logging_config:
            logging.config.dictConfig(logging_config)
        self.log = functools.partial(logging.log, extra=dict(source=f"{name} Worker"))

        self.name = name

        # Keep hold of the shutdown event so that we can share it with our
        # ProcWorker, and at some point set it to commence shutdown. Note that
        # this shutdown event is shared with the MainContext and all other
        # Procs - and hence, with their ProcWorkers too.
        self.shutdown_event = shutdown_event

        # Create an event that will be set by the ProcWorker to indicate when
        # startup is complete.
        self.startup_event = mp.Event()

        # Prepare a new multiprocessing Process that will, when started, cause
        # proc_worker_wrapper (the ProcWorker constructor helper function) to
        # run in a new Process. This will create the ProcWorker instance to be
        # created in a new child Python process. As the ProcWorker runs in an
        # independent Python interpreter, communication with this Proc is only
        # possible via the queues and events passed to it in this call.
        self.proc = mp.Process(
            target=proc_worker_wrapper,
            name=name,
            args=(
                worker_class,
                name,
                self.startup_event,
                shutdown_event,
                event_q,
                *args,
            ),
            kwargs=dict(logging_config=logging_config, **kwargs),
        )

        # At this point the mp.Process has been instantiated, but it's not yet
        # running. Calling start() will cause the new interpreter to be
        # launched and the ProcWorker to start executing. If the ProcWorker
        # starts successfully, it will set the startup event.
        self.log(logging.DEBUG, "Proc.__init__ starting: %s", name)
        self.proc.start()
        started = self.startup_event.wait(timeout=Proc.STARTUP_WAIT_SECS)
        self.log(logging.DEBUG, "Proc.__init__ starting: %s got %s", name, started)

        # If the event remains unset, startup failed (or we didn't wait long
        # enough - we're assuming STARTUP_WAIT_SECS is sufficient!), in which
        # case terminate the process and raise an exception.
        if not started:
            self.terminate()
            raise RuntimeError(
                f"Process {name} failed to startup after {Proc.STARTUP_WAIT_SECS} "
                "seconds"
            )

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
        self.log(logging.DEBUG, "Proc.full_stop stopping %s", self.name)
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
        self.log(logging.DEBUG, "Proc.terminate terminating %s", self.name)
        attempt = 0
        while self.proc.is_alive():
            self.proc.terminate()
            self.proc.join(timeout)
            attempt += 1
            if attempt >= max_retries:
                break

        # Insufficient timeout can mean pycoverage cleanup is still running at
        # this point even if the ProcWorker loop ended and all OET code
        # completed. This gives a misleading .is_alive(), breaking the
        # hung_soft unit test

        if self.proc.is_alive():
            self.log(
                logging.ERROR,
                "Proc.terminate failed to terminate %s after %s attempts",
                self.name,
                attempt,
            )
            return False
        else:
            self.log(
                logging.INFO,
                "Proc.terminate terminated %s after %s attempt(s)",
                self.name,
                attempt,
            )
            return True


# -- Main Wrappers
class MainContext:
    """
    MainContext is the parent context for a set of worker processes that
    communicate via message queues.
    """

    # Grace period after setting shutdown_event before processes are forcibly terminated
    STOP_WAIT_SECS = 3.0

    # Seconds to wait for processes to respond to terminate before retrying
    TERMINATE_TIMEOUT_SECS = 0.1

    def __init__(self):
        self.procs: List[Proc] = []
        self.queues: List[MPQueue] = []
        self.log = functools.partial(logging.log, extra=dict(source="MAIN"))

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
            self.log(
                logging.ERROR,
                f"Exception: {exc_val}",
                exc_info=(exc_type, exc_val, exc_tb),
            )

        # pylint: disable=attribute-defined-outside-init
        # these instance props are required for test validation
        self._stopped_procs_result = self.stop_procs()
        self._stopped_queues_result = self.stop_queues()

        # -- Don't eat exceptions that reach here.
        return not exc_type

    def Proc(self, name: str, worker_class: Type[ProcWorker], *args, **kwargs) -> Proc:
        """
        Create a new process managed by this context.

        :param name: name for worker process
        :param worker_class: worker process class
        :param args: argument to pass to worker constructor
        :return: worker instance
        """
        proc = Proc(
            name,
            worker_class,
            self.shutdown_event,
            self.event_queue,
            *args,
            logging_config=self.logging_config,
            **kwargs,
        )
        self.procs.append(proc)
        return proc

    def MPQueue(self, *args, **kwargs) -> MPQueue:
        """
        Create a new message queue managed by this context.

        :param args: queue constructor args
        :param kwargs: queue constructor kwargs
        :return: message queue instance
        """
        queue = MPQueue(*args, **kwargs)
        self.queues.append(queue)
        return queue

    def stop_procs(self) -> Tuple[int, int]:
        """
        Stop all ProcWorkers managed by this MPContext.

        stop_procs requests cooperative shutdown of running ProcWorkers before
        escalating to more forceful methods using POSIX signals.

        This function returns with a 2-tuple, the first item indicating the
        number of ProcWorkers that returned a non-zero exit status on
        termination, the second item indicating the number of ProcWorkers that
        required termination.

        :return: tuple of process termination stats
        """
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
                if proc.terminate(timeout=self.TERMINATE_TIMEOUT_SECS):
                    num_terminated += 1
                else:
                    still_running.append(proc)
            else:
                exitcode = proc.proc.exitcode
                if exitcode:
                    self.log(
                        logging.ERROR,
                        f"Process {proc.name} ended with exitcode {exitcode}",
                    )
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
        for queue in self.queues:
            num_items_left += sum(1 for __ in queue.drain())
            queue.close()

        # Wait for all queue threads to stop
        while self.queues:
            queue = self.queues.pop(0)
            queue.join_thread()

        return num_items_left
