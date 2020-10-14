# -*- coding: utf-8 -*-

"""Top-level package for Multiprocessing Tools.

This package is substantially based on Pamela D McA'Nulty's mptools project,
which is hosted at

  https://github.com/PamelaM/mptools

Pamela presents an excellent article given an overview of the MPTools package
at

  https://www.cloudcity.io/blog/2019/02/27/things-i-wish-they-told-me-about-multiprocessing-in-python/

-------------------------------------------------------------------------------

MPTools is subject to the MIT licence.

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

__author__ = """Pamela D McA'Nulty"""
__email__ = 'pamela@mcanulty.org'
__version__ = '0.2.1'

from ._mptools import (
    MPQueue,
    _sleep_secs,
    SignalObject,
    init_signal,
    init_signals,
    default_signal_handler,
    ProcWorker,
    proc_worker_wrapper,
    TimerProcWorker,
    QueueProcWorker,
    Proc,
    EventMessage,
    MainContext,
    TerminateInterrupt,
)
__all__ = [
    'MPQueue',
    '_sleep_secs',
    'SignalObject',
    'init_signal',
    'init_signals',
    'default_signal_handler',
    'ProcWorker',
    'proc_worker_wrapper',
    'TimerProcWorker',
    'QueueProcWorker',
    'Proc',
    'EventMessage',
    'MainContext',
    'TerminateInterrupt',
]
