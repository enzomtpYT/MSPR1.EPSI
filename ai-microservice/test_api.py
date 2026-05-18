import urllib.request, json

# Test health
req = urllib.request.urlopen("http://localhost:8001/api/v1/health")
print("=== HEALTH ===")
print(json.loads(req.read()))

# Test nutrition (user 2 = Bob, muscle_gain)
print("\n=== NUTRITION RECOMMENDATION (user 2 / muscle_gain) ===")
payload = json.dumps({"user_id": 2, "nb_meals_per_day": 4}).encode()
req = urllib.request.Request(
    "http://localhost:8001/api/v1/nutrition/recommend",
    data=payload, headers={"Content-Type": "application/json"}, method="POST"
)
data = json.loads(urllib.request.urlopen(req).read())
print(f"recommendation_id : {data['recommendation_id']}")
print(f"model_version     : {data['model_version']}")
print(f"macro_targets     : {data['macro_targets']}")
print(f"meal_plan ({len(data['meal_plan'])} repas) :")
for m in data["meal_plan"]:
    print(f"  {m['meal_slot']:30s} -> {m['product_name']:20s} {m['kcal']:.0f} kcal")
print(f"warnings          : {data.get('warnings')}")

# Test workout (user 2 = Bob)
print("\n=== WORKOUT RECOMMENDATION (user 2 / muscle_gain) ===")
payload = json.dumps({"user_id": 2, "sessions_per_week": 4}).encode()
req = urllib.request.Request(
    "http://localhost:8001/api/v1/workout/recommend",
    data=payload, headers={"Content-Type": "application/json"}, method="POST"
)
data = json.loads(urllib.request.urlopen(req).read())
print(f"recommendation_id     : {data['recommendation_id']}")
print(f"model_version         : {data['model_version']}")
print(f"fitness_level_detected: {data['fitness_level_detected']}")
print(f"weekly_plan ({len(data['weekly_plan'])} seances) :")
for s in data["weekly_plan"]:
    print(f"  Jour {s['day']} | {s['workout_type']:12s} | {s['intensity']:8s} | {s['duration_min']} min | {len(s['exercises'])} exercices")
print(f"adaptive_notes        : {data.get('adaptive_notes')}")
