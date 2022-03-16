# pylint: disable=W0221,W0613,W0212
# - W0221(arguments-differ) - ignore complaints about test ProcWorkers
#   removing variadic args from API. These test workers don't use them anyway.
# - W0613(unused-argument) - these are fixtures, not function args
# - W0212(protected-access) - tests need access to protected members to prove
#   correctness
"""
Unit tests for mptools package.
"""
import logging
import multiprocessing as mp
import os
import signal
import time

import pytest

from ska_oso_oet.mptools import (
    MainContext,
    MPQueue,
    Proc,
    ProcWorker,
    QueueProcWorker,
    SignalObject,
    TerminateInterrupt,
    TimerProcWorker,
    _sleep_secs,
    default_signal_handler,
    init_signal,
    proc_worker_wrapper,
)

# Seconds to wait for the coverage cleanup function to complete before
# assessing process liveness
COVERAGE_PROCESS_END_OVERHEAD_SECS = 0.5


@pytest.fixture(autouse=True)
def restore_default_signal_handlers():
    original_sigint_handler = signal.getsignal(signal.SIGINT)
    original_sigterm_handler = signal.getsignal(signal.SIGTERM)
    try:
        yield
    finally:
        signal.signal(signal.SIGINT, original_sigint_handler)
        signal.signal(signal.SIGTERM, original_sigterm_handler)


def test_mpqueue_get():
    Q = MPQueue()

    item = Q.safe_get(None)
    assert item is None

    Q.put("ITEM1")
    Q.put("ITEM2")

    assert Q.safe_get(0.02) == "ITEM1"
    assert Q.safe_get(0.02) == "ITEM2"
    assert Q.safe_get(0.02) is None
    assert Q.safe_get(None) is None

    num_left = Q.safe_close()
    assert num_left == 0


def test_queue_put():
    # Create MPQueue of max size 2
    q = MPQueue(2)
    # Putting two items should succeed and return True
    assert q.safe_put("ITEM1")
    assert q.safe_put("ITEM2")
    # But once full, puts should return False
    assert not q.safe_put("ITEM3")

    num_left = q.safe_close()
    assert num_left == 2


def test_drain_queue():
    Q = MPQueue()

    items = list(Q.drain())
    assert items == []

    expected = [f"ITEM{idx}" for idx in range(10)]
    for item in expected:
        Q.put(item)

    items = list(Q.drain())
    assert items == expected

    num_left = Q.safe_close()
    assert num_left == 0


def test_sleep_secs():
    # if deadline has passed already, should not sleep
    assert _sleep_secs(5.0, time.time() - 1.0) == 0.0
    # if deadline is in future and delay occurs before deadline, should sleep delay secs
    assert _sleep_secs(1.0, time.time() + 5.0) == 1.0

    end_time = time.time() + 4.0
    got = _sleep_secs(5.0, end_time)
    assert got <= 4.0
    assert got >= 3.7


def test_signal_handling():
    pid = os.getpid()
    evt = mp.Event()
    so = SignalObject(evt)

    class MyException(Exception):
        pass

    init_signal(signal.SIGINT, so, MyException, default_signal_handler)
    # a pristine SignalObject should have shutdown_event unset and no
    # terminate calls recorded
    assert so.terminate_called == 0
    assert not so.shutdown_event.is_set()

    # But once the signal handler is invoked, the shutdown_event should be set
    # and the number of termination calls incremented
    for i in range(1, so.MAX_TERMINATE_CALLED):
        os.kill(pid, signal.SIGINT)
        assert so.terminate_called == i
        assert so.shutdown_event.is_set()

    # but once the MAX_TERMINATE_CALLED threshold is reached, the requested
    # exception is raised
    with pytest.raises(MyException):
        os.kill(pid, signal.SIGINT)
    # While the event and counter remain set accordingly
    assert so.terminate_called == so.MAX_TERMINATE_CALLED
    assert so.shutdown_event.is_set()


def test_procworker_rejects_unexpected_arguments():
    with pytest.raises(ValueError):
        ProcWorker("TEST", mp.Event(), mp.Event(), MPQueue(), MPQueue(), "ARG1", "ARG2")


def test_procworker_passes_excess_arguments_to_init_args():
    class ProcWorkerTest(ProcWorker):
        def init_args(self, args):
            (l,) = args
            l.extend(["ARG1", "ARG2"])

    arglist = []
    ProcWorkerTest("TEST", mp.Event(), mp.Event(), MPQueue(), arglist)
    assert arglist == ["ARG1", "ARG2"]


def test_proc_worker_init_signals():
    pid = os.getpid()
    evt = mp.Event()
    pw = ProcWorker("TEST", 1, evt, 3)
    so = pw.init_signals()

    assert not so.shutdown_event.is_set()
    assert so.terminate_called == 0

    os.kill(pid, signal.SIGINT)
    assert so.terminate_called == 1
    assert so.shutdown_event.is_set()

    os.kill(pid, signal.SIGINT)
    assert so.terminate_called == 2
    assert so.shutdown_event.is_set()

    with pytest.raises(KeyboardInterrupt):
        os.kill(pid, signal.SIGINT)

    assert so.terminate_called == 3
    assert so.shutdown_event.is_set()


def test_proc_worker_no_main_func(caplog):
    startup_evt = mp.Event()
    shutdown_evt = mp.Event()
    event_q = MPQueue()

    try:
        caplog.set_level(logging.INFO)
        pw = ProcWorker("TEST", startup_evt, shutdown_evt, event_q)
        with pytest.raises(NotImplementedError):
            pw.main_func()

    finally:
        event_q.safe_close()


def test_proc_worker_run(caplog):
    class ProcWorkerTest(ProcWorker):
        def init_args(self, args):
            self.args = args

        def main_func(self):
            self.log(logging.INFO, f"MAIN_FUNC: {self.args}")
            self.shutdown_event.set()

    startup_evt = mp.Event()
    shutdown_evt = mp.Event()
    event_q = MPQueue()

    caplog.set_level(logging.INFO)
    pw = ProcWorkerTest("TEST", startup_evt, shutdown_evt, event_q, "ARG1", "ARG2")
    assert not startup_evt.is_set()
    assert not shutdown_evt.is_set()

    pw.run()

    assert startup_evt.is_set()
    assert shutdown_evt.is_set()
    item = event_q.safe_get()
    assert item
    assert item.msg_src == "TEST"
    assert item.msg_type == "SHUTDOWN"
    assert item.msg == "Normal"
    assert "MAIN_FUNC: ('ARG1', 'ARG2')" in caplog.text


def _proc_worker_wrapper_helper(
    caplog, worker_class, args=None, expect_shutdown_evt=True, alarm_secs=1.0
):
    startup_evt = mp.Event()
    shutdown_evt = mp.Event()
    event_q = MPQueue()
    if args is None:
        args = ()

    def alarm_handler(signal_num, current_stack_frame):
        shutdown_evt.set()

    if alarm_secs:
        signal.signal(signal.SIGALRM, alarm_handler)
        signal.setitimer(signal.ITIMER_REAL, alarm_secs)
    caplog.set_level(logging.DEBUG)
    exitcode = proc_worker_wrapper(
        worker_class, "TEST", startup_evt, shutdown_evt, event_q, *args
    )
    assert startup_evt.is_set()
    assert shutdown_evt.is_set() == expect_shutdown_evt
    items = list(event_q.drain())
    assert items
    last_item = items[-1]
    assert last_item.msg_src == "TEST"
    assert last_item.msg_type == "SHUTDOWN"
    assert last_item.msg == "Normal"
    assert exitcode == 0

    return items[:-1]


def test_proc_worker_wrapper(caplog):
    class ProcWorkerTest(ProcWorker):
        def init_args(self, args):
            self.args = args

        def main_func(self):
            self.log(logging.INFO, f"MAIN_FUNC: {self.args}")
            self.shutdown_event.set()

    items = _proc_worker_wrapper_helper(caplog, ProcWorkerTest, ("ARG1", "ARG2"))
    assert not items
    assert "MAIN_FUNC: ('ARG1', 'ARG2')" in caplog.text


def test_proc_worker_exception(caplog):
    class ProcWorkerException(ProcWorker):
        def main_func(self):
            raise NameError("Because this doesn't happen often")

    startup_evt = mp.Event()
    shutdown_evt = mp.Event()
    event_q = MPQueue()

    caplog.set_level(logging.INFO)
    with pytest.raises(SystemExit):
        proc_worker_wrapper(
            ProcWorkerException, "TEST", startup_evt, shutdown_evt, event_q
        )
    assert startup_evt.is_set()
    assert not shutdown_evt.is_set()
    item = event_q.safe_get()
    assert item
    assert item.msg_src == "TEST"
    assert item.msg_type == "FATAL"
    assert item.msg == "Because this doesn't happen often"

    assert "Exception Shutdown" in caplog.text


class TimerProcWorkerTest(TimerProcWorker):
    INTERVAL_SECS = 0.01
    times_called = 0

    def main_func(self):
        self.times_called += 1
        self.event_q.put(f"TIMER {self.times_called} [{time.time()}]")
        if self.times_called >= 4:
            self.shutdown_event.set()


def test_timer_proc_worker(caplog):
    items = _proc_worker_wrapper_helper(caplog, TimerProcWorkerTest)
    assert len(items) == 4
    for idx, item in enumerate(items[:-1]):
        assert item.startswith(f"TIMER {idx + 1} [")


class QueueProcWorkerTest(QueueProcWorker):
    def main_func(self, item):
        self.event_q.put(f"DONE {item}")


def test_queue_proc_worker(caplog):
    work_q = MPQueue()
    work_q.put(1)
    work_q.put(2)
    work_q.put(3)
    work_q.put(4)
    work_q.put("END")
    work_q.put(5)

    items = _proc_worker_wrapper_helper(
        caplog, QueueProcWorkerTest, args=(work_q,), expect_shutdown_evt=False
    )
    assert len(items) == 4
    assert items == [f"DONE {idx + 1}" for idx in range(4)]


class StartHangWorker(ProcWorker):
    def startup(self, *_):
        while True:
            time.sleep(1.0)


def test_proc_start_hangs(caplog):
    shutdown_evt = mp.Event()
    event_q = MPQueue()
    log_q = MPQueue()
    caplog.set_level(logging.INFO)
    Proc.STARTUP_WAIT_SECS = 0.2
    try:
        with pytest.raises(RuntimeError):
            Proc("TEST", StartHangWorker, shutdown_evt, event_q, log_q)
    finally:
        Proc.STARTUP_WAIT_SECS = 3.0


def test_proc_full_stop(caplog):
    shutdown_evt = mp.Event()
    event_q = MPQueue()
    caplog.set_level(logging.INFO)
    proc = Proc("TEST", TimerProcWorkerTest, shutdown_evt, event_q)

    for idx in range(4):
        item = event_q.safe_get(1.0)
        assert item, f"idx: {idx}"
        assert item.startswith(f"TIMER {idx + 1} [")

    item = event_q.safe_get(1.0)
    assert item.msg_src == "TEST"
    assert item.msg_type == "SHUTDOWN"
    assert item.msg == "Normal"

    proc.full_stop(wait_time=0.5)

    assert not proc.proc.is_alive()


class NeedTerminateWorker(ProcWorker):
    def main_loop(self):
        while True:
            time.sleep(1.0)


def test_proc_full_stop_need_terminate(caplog):
    shutdown_evt = mp.Event()
    event_q = MPQueue()
    caplog.set_level(logging.INFO)
    proc = Proc("TEST", NeedTerminateWorker, shutdown_evt, event_q)
    proc.full_stop(wait_time=0.1)
    # additional delay is required for coverage cleanup to complete, at which
    # point the process will _finally_ be dead
    proc.proc.join(timeout=COVERAGE_PROCESS_END_OVERHEAD_SECS)
    assert not proc.proc.is_alive()


def test_main_context_stop_queues():
    with MainContext() as mctx:
        q1 = mctx.MPQueue()
        q1.put("SOMETHING 1")
        q2 = mctx.MPQueue()
        q2.put("SOMETHING 2")

    # -- 4 == the 2 queued items in this test, and the END event
    assert mctx._stopped_queues_result == 3


def _test_stop_procs(cap_log, proc_name, worker_class, *args):
    """
    Arrange for stop_procs to be called on a running worker class, collecting
    stats on whether the worker was identified as failing, responding to
    forcible termination, or zombie (not responding to shutdown events o
    Terminateinterrupts).
    """
    cap_log.set_level(logging.DEBUG)
    with MainContext() as mctx:
        # Reduce grace period before MainContext starts terminating Procs for
        # quicker testing. IMPORTANT! This delay must be sufficient for
        # coverage to complete cleanup, which is registered as an atexit
        # function to be run on subprocess exit. The _clean test will fail if
        # this delay is insufficient, as the process will still be alive and
        # running coverage code when the MainContext checks shutdown state,
        # making it think further termination is required.
        mctx.STOP_WAIT_SECS = COVERAGE_PROCESS_END_OVERHEAD_SECS
        # Just as for STOP_WAIT_SECS, this must be sufficient for coverage
        # cleanup to complete. This affects the hung_soft test, where the
        # main loop exits but the cleanup routine keeps the ProcWorker alive.
        mctx.TERMINATE_TIMEOUT_SECS = COVERAGE_PROCESS_END_OVERHEAD_SECS
        mctx.Proc(proc_name, worker_class, *args)

    # send SIGTERM again, thus ending the hard_hang worker that ignores the
    # first TerminateInterrupt but respects the second
    for proc in mctx.procs:
        proc.terminate()

    # MainContext.stop_procs is called as the context manager completes, which
    # then sets _stopped_procs_result. It's private but contains the stats we
    # need.
    num_failed, num_terminated = mctx._stopped_procs_result
    num_still_running = len(mctx.procs)
    return num_failed, num_terminated, num_still_running


def test_main_context_exception():
    """
    Verify that MainContext does not swallow exceptions raised while the
    MainContext is in scope.
    """
    with pytest.raises(ValueError):
        with MainContext():
            raise ValueError("Yep, this is a value Error")


class CleanProcWorker(ProcWorker):
    """
    Well-behaved process that completes successfully
    """

    def main_func(self):
        pass


def test_main_context_stop_procs_clean(caplog):
    num_failed, num_terminated, num_still_running = _test_stop_procs(
        caplog, "CLEAN", CleanProcWorker
    )
    assert num_failed == 0
    assert num_terminated == 0
    assert num_still_running == 0


class FailProcWorker(ProcWorker):
    """
    Worker process that always raises an exception in its main loop.
    """

    def main_func(self):
        raise ValueError("main func value error")


def test_main_context_stop_procs_fail(caplog):
    """
    Verify stop_procs behaviour for a ProcWorker that fails due to an
    exception.
    """
    caplog.set_level(logging.DEBUG)
    num_failed, num_terminated, num_still_running = _test_stop_procs(
        caplog, "FAIL", FailProcWorker
    )
    assert num_failed == 1
    assert num_terminated == 0
    assert num_still_running == 0


class HangingProcWorker(ProcWorker):
    """
    A ProcWorker that ignores shutdown_event, forcing the signal handler to
    raise TerminateInterrupts. The worker main loop will end on the first
    TerminateInterrupt when if is_hard is False, or on the second
    TerminateInterrupt when is_hard is True.
    """

    def init_args(self, args):
        (self.is_hard,) = args

    def main_loop(self):
        # note that main_loop ignores shutdown_event, forcing the signal
        # handler to start raising TerminateInterrupts.
        MAX_TERMINATES = 2 if self.is_hard else 1
        num_terminates = 0
        while num_terminates < MAX_TERMINATES:
            try:
                while True:
                    time.sleep(5.0)
            except TerminateInterrupt:
                num_terminates += 1
        self.log(
            level=logging.DEBUG,
            msg=f"Terminating HangingProcworker loop after {num_terminates} signals",
        )


def _test_main_context_hang(cap_log, is_hard):
    return _test_stop_procs(cap_log, "HANG", HangingProcWorker, is_hard)


def test_main_context_stop_procs_hung_soft(caplog):
    """
    Verify stop_procs behaviour when processes do not respond to settomg
    shutdown events but does respond to TerminateInterrupt.
    """
    num_failed, num_terminated, num_still_running = _test_main_context_hang(
        caplog, is_hard=False
    )
    assert num_failed == 0
    assert num_terminated == 1
    assert num_still_running == 0


def test_main_context_stop_procs_hung_hard(caplog):
    """
    Verify stop_procs behaviour when processes do not respond to setting
    shutdown event or to TerminateInterrupts.
    """
    num_failed, num_terminated, num_still_running = _test_main_context_hang(
        caplog, is_hard=True
    )
    assert num_failed == 0
    assert num_terminated == 0
    assert num_still_running == 1
