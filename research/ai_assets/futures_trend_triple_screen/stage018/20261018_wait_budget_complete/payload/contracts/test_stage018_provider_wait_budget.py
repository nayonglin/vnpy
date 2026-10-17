"""Offline controls for one provider instance and one total wait budget."""
import unittest
import pandas as pd

try:
    import stage018_provider_wait_budget as module
except ImportError:
    module=None


class Clock:
    def __init__(self):self.now=0.
    def monotonic(self):return self.now
    def wall(self):return 1000.+self.now


class FakeCollector:
    def __init__(self):self.records={};self.target_count=1
    def observe(self,symbol,serial,initial=False):self.records[symbol]='completed'


class FakeApi:
    def __init__(self,clock,events):self.clock=clock;self.events=iter(events);self.calls=0
    def wait_update(self,deadline):
        self.calls+=1
        event=next(self.events,False)
        if isinstance(event,BaseException):raise event
        self.clock.now+=deadline-self.clock.wall() if event is False else 1.
        return event
    def is_serial_ready(self,serial):return True


class WaitBudgetTests(unittest.TestCase):
    def run_loop(self,events):
        self.assertIsNotNone(module,'Stage018 not implemented')
        clock=Clock();api=FakeApi(clock,events);collector=FakeCollector();diagnostic={};saves=[]
        serials={'AP210.CZCE':pd.DataFrame({'datetime':[1]})}
        status=module.collect_with_budget(api,collector,serials,0.,diagnostic,
            lambda:saves.append(dict(diagnostic)),monotonic=clock.monotonic,wall_clock=clock.wall)
        return status,api,collector,diagnostic,saves,clock

    def test_false_false_true_recovers_on_same_provider(self):
        status,api,collector,diagnostic,saves,clock=self.run_loop([False,False,True])
        self.assertEqual(status,'all_target_minutes_completed')
        self.assertEqual(api.calls,3);self.assertEqual(len(collector.records),1)
        self.assertEqual(diagnostic['idle_waits'],2)
        self.assertEqual([x['phase']for x in saves[:2]],['wait_update_returned_false']*2)
        self.assertEqual(clock.now,61.)

    def test_continuous_false_exhausts_one_total_budget(self):
        status,api,collector,diagnostic,saves,clock=self.run_loop([])
        self.assertEqual(status,'soft_time_budget_reached')
        self.assertEqual(api.calls,19);self.assertEqual(clock.now,570.)
        self.assertEqual(diagnostic['idle_waits'],19)
        self.assertEqual(collector.records,{})

    def test_real_exception_stops_without_second_wait(self):
        self.assertIsNotNone(module,'Stage018 not implemented')
        clock=Clock();api=FakeApi(clock,[PermissionError('not persisted'),True]);diagnostic={}
        with self.assertRaises(PermissionError):
            module.collect_with_budget(api,FakeCollector(),{},0.,diagnostic,lambda:None,
                monotonic=clock.monotonic,wall_clock=clock.wall)
        self.assertEqual(api.calls,1)
        self.assertEqual(diagnostic['phase'],'wait_update_raised')


if __name__=='__main__':unittest.main()
