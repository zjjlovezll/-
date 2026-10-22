import json
c = json.load(open("diagnostics/crh380a_m_track_catalog.json", encoding="utf-8"))
print(list(c.keys()))
print("left refs:", [(r["index"], r["station_m"], r["path"].split("\\")[-1]) for r in c["profile_references"] if r["side"]=="left"])
print("right refs first 3:", [(r["index"], r["station_m"], r["path"].split("\\")[-1]) for r in c["profile_references"] if r["side"]=="right"][:3])
print("coincident[0]:", c["coincident_stations"][0])
print("wheel:", c["wheel_profiles_referenced_directly"][0]["path"])
print("has source_model_sha256:", "source_model_sha256" in c, " profile_set_sha256:", c.get("profile_set_sha256"))
