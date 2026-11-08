"""作者：Wangyuan；日期：2026-10-29。完全合成的离线库调用演示。"""
import argparse,json
argparse.ArgumentParser(description="纯合成数据演示，不联网，不读取原业务目录").parse_args()
from dataclasses import asdict
from simulation.distribution import DurationDistribution
from simulation.events.entities import FlightOccurrence,FlightVersion
from simulation.events.solver import DurationComponents,solve_events
result=solve_events(flight=FlightVersion("v1","f1","p1",100,200,"UTC","UTC","SYNTH",None,"synthetic"),occurrence=FlightOccurrence("f1","synthetic",None,"ZZ","100","2040-01-01","XXXX","YYYY",1),earliest_aobt=100,durations=DurationComponents(10,60,10),cutoff_at=99)
distribution=DurationDistribution((10,20),(.25,.75))
print(json.dumps({"synthetic":True,"conditional_events":asdict(result),"median_seconds":distribution.quantile(.5),"probability_above_10":distribution.exceed_probability(10)},ensure_ascii=False,indent=2))
