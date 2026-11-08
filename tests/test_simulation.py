"""作者：Wangyuan；日期：2026-10-29。合成分布与事件窗口回归。"""
import unittest,math
from datetime import date,datetime,timedelta,timezone
from simulation.distribution import DurationDistribution
from simulation import robust,risk,samples,constraints,chains,recovery_math
from simulation.sample_models import SegmentSample
from simulation.chain_models import FlightOccurrence,CandidateAobt
from simulation.events.asof import ArtifactAvailability,visibility
from simulation.events.solver import EventWindow,WaitLocation,check_event_window
from simulation.events.enums import EventType,HardCheck
class SimulationTests(unittest.TestCase):
    def test_distribution(self):
        dist=DurationDistribution((10,20),(.25,.75));self.assertEqual(dist.quantile(.25),10);self.assertEqual(dist.quantile(.26),20);self.assertEqual(dist.exceed_probability(10),.75);self.assertEqual(dist.expected_positive_gap(15),3.75)
    def test_distribution_merge(self):
        dist=DurationDistribution((10,10,20),(.2,.3,.5));self.assertEqual(dist.seconds,(10,20));self.assertEqual(dist.probabilities,(.5,.5))
    def test_bad_distribution(self):
        for values,probs in [((1,),(.5,)),((float("nan"),),(1,)),((-1,),(1,))]:
            with self.subTest(values=values),self.assertRaises(ValueError):DurationDistribution(values,probs)
    def test_quantile_boundary(self):
        dist=DurationDistribution((1,2),(.5,.5));self.assertEqual(dist.quantile(0),1);self.assertEqual(dist.quantile(1),2)
        with self.assertRaises(ValueError):dist.quantile(1.1)
    def test_percentiles(self):
        self.assertEqual(robust.percentile([10,20,30],.5),20)
    def test_robust_explicit(self):
        result=robust.robust_filter([10,10,10,10,100],minimum_samples=4,mad_limit=3,absolute_jitter=1,relative_jitter=0,minimum_retained=2,retention_fraction=.5)
        self.assertEqual(result.values,(10,10,10,10))
    def test_robust_invalid(self):
        with self.assertRaises(ValueError):robust.robust_filter([1,2],minimum_samples=0,mad_limit=3,absolute_jitter=1,relative_jitter=0,minimum_retained=1,retention_fraction=.5)
    def test_huber(self):
        value=robust.huber_location([1,1,1,100]);self.assertLess(value,30)
    def test_visibility(self):
        self.assertTrue(visibility(1,2,3,snapshot_ref="synthetic").eligible);self.assertFalse(visibility(1,4,3,snapshot_ref="synthetic").eligible)
    def test_visibility_missing(self):
        self.assertFalse(visibility(None,1,3,snapshot_ref="synthetic").eligible)
    def test_sample_aggregation(self):
        data=[SegmentSample(str(i),str(i),"A-B","2040-01-01","SYNTH",100,120,None,None,None,"explicit",source_mode="synthetic") for i in range(2)]
        result=samples.aggregate_window("custom",date(2040,1,1),date(2040,1,2),data,110,formal=2,review=1,high=3)
        self.assertEqual(result.average_paired_gap_seconds,20);self.assertEqual(result.current_plan_gap_seconds,10)
    def test_window_ranges_explicit(self):
        self.assertEqual(samples.window_ranges(date(2040,1,31),date(2040,1,1))["season_to_date"],(date(2040,1,1),date(2040,1,30)))
    def test_constraint_winners(self):
        when=datetime(2040,1,1,tzinfo=timezone.utc);best,winners,_=constraints.max_constraint_aobt([CandidateAobt(when,"a",""),CandidateAobt(when+timedelta(hours=1),"b","",False)])
        self.assertEqual(best,when);self.assertEqual(len(winners),1)
    def test_constraint_window(self):
        when=datetime(2040,1,1,tzinfo=timezone.utc);window=constraints.ctot_window(when,2,3);self.assertTrue(window.contains(when-timedelta(minutes=2)))
        with self.assertRaises(ValueError):constraints.ctot_window(when,-1,3)
    def test_chains_conflict(self):
        data=[FlightOccurrence("one","2040-01-01","S1","A","B",plane_no="SYNTH",dep_plan=datetime(2040,1,1,1,tzinfo=timezone.utc)),FlightOccurrence("two","2040-01-01","S2","C","D",plane_no="SYNTH",dep_plan=datetime(2040,1,1,2,tzinfo=timezone.utc))]
        result,warnings=chains.build_chains(data);self.assertTrue(result[0].conflict);self.assertTrue(warnings)
    def test_cancelled_no_chain(self):
        data=[FlightOccurrence("one","2040-01-01","S1","A","B",plane_no="SYNTH",result_kind="cancelled")]
        self.assertEqual(chains.build_chains(data)[0],[])
    def test_missing_aircraft_plan_only(self):
        result,_=chains.build_chains([FlightOccurrence("one","2040-01-01","S1","A","B")]);self.assertTrue(result[0].is_plan_only)
    def test_recovery_absorption(self):
        base=datetime(2040,1,1,tzinfo=timezone.utc);legs=[recovery_math.FlightLeg(base,base+timedelta(hours=1)),recovery_math.FlightLeg(base+timedelta(hours=2),base+timedelta(hours=3))]
        self.assertEqual(recovery_math.propagated_delays(legs,50,minimum_turnaround_minutes=20),[50,10])
    def test_recovery_invalid(self):
        with self.assertRaises(ValueError):recovery_math.propagated_delays([],1,minimum_turnaround_minutes=-1)
    def event_inputs(self):
        from simulation.events.entities import FlightVersion,FlightOccurrence
        from simulation.events.solver import DurationComponents
        return dict(flight=FlightVersion("v1","f1","p1",100,200,"UTC","UTC","SYNTH",None,"synthetic"),occurrence=FlightOccurrence("f1","synthetic",None,"ZZ","100","2040-01-01","XXXX","YYYY",1),earliest_aobt=100,durations=DurationComponents(10,60,10),cutoff_at=99)
    def test_event_solver_full(self):
        from simulation.events.solver import solve_events
        result=solve_events(**self.event_inputs());self.assertEqual((result.aobt,result.atot,result.aldt,result.aibt),(100,110,170,180));self.assertEqual(result.status,HardCheck.PASS)
    def test_event_solver_wait(self):
        from simulation.events.solver import solve_events
        window=EventWindow("synthetic","XXXX",EventType.ATOT,150,200,"[)",(WaitLocation.GATE,),ArtifactAvailability("s",1,2,"snapshot"))
        result=solve_events(**self.event_inputs(),constraints=(window,));self.assertEqual(result.atot,150);self.assertEqual(result.aobt,140)
    def test_event_solver_future_source(self):
        from simulation.events.solver import solve_events
        window=EventWindow("synthetic","XXXX",EventType.ATOT,150,200,"[)",(WaitLocation.GATE,),ArtifactAvailability("s",1000,1001,"snapshot"))
        result=solve_events(**self.event_inputs(),constraints=(window,));self.assertEqual(result.status,HardCheck.UNKNOWN);self.assertIsNone(result.aobt)
    def test_event_solver_partial(self):
        from simulation.events.solver import solve_events,DurationComponents
        data=self.event_inputs();data["durations"]=DurationComponents(block_seconds=80);result=solve_events(**data);self.assertIsNone(result.atot);self.assertEqual(result.aibt,180)
    def test_event_duration_conflict(self):
        from simulation.events.solver import DurationComponents
        with self.assertRaises(ValueError):DurationComponents(10,60,10,100)

if __name__=="__main__":unittest.main()
