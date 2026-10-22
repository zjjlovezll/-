import json
src=r"validation\crh380a_m\case_bench_0.json"
c=json.load(open(src,encoding="utf-8"))
c["run"]["duration_s"]=0.005
c["run"]["output_step_s"]=0.0005
json.dump(c,open(r"validation\crh380a_m\case_tiny.json","w",encoding="utf-8"),ensure_ascii=False,indent=1)
print("tiny case: duration",c["run"]["duration_s"],"x_start",c["run"]["x_start_m"])
