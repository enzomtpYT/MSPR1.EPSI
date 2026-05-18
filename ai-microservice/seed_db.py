"""
Seed script — insère des données de test dans mspr_db
pour tester les endpoints du microservice IA.
"""

import datetime
from sqlalchemy import create_engine, text

url = "postgresql://postgres:postgres@localhost:5432/mspr_db"
engine = create_engine(url)

with engine.begin() as conn:

    # ---------- Utilisateurs ----------
    conn.execute(text("""
        INSERT INTO users ("User_ID","User_mail","User_password","isAdmin",
                           "User_Subscription","User_age","User_weight","User_Height",
                           "User_gender","User_Goals","User_Allergies",
                           "User_Dietary_Preferences","User_Budget_Level","User_Injuries",
                           "created_at","updated_at")
        VALUES
          (1,'alice@test.com','$2b$12$hashalice',false,
           'free',28,60.0,165.0,
           'female','weight_loss',ARRAY[]::text[],ARRAY['vegan'],'low',ARRAY[]::text[],
           NOW(),NOW()),
          (2,'bob@test.com','$2b$12$hashbob',false,
           'premium',35,85.0,180.0,
           'male','muscle_gain',ARRAY[]::text[],ARRAY[]::text[],'medium',ARRAY[]::text[],
           NOW(),NOW()),
          (3,'carol@test.com','$2b$12$hashcarol',true,
           'free',42,70.0,170.0,
           'female','maintenance',ARRAY[]::text[],ARRAY['vegetarian'],'medium',ARRAY['knee'],
           NOW(),NOW())
        ON CONFLICT ("User_ID") DO NOTHING
    """))

    # ---------- Produits ----------
    conn.execute(text("""
        INSERT INTO products ("Product_ID","product_name","product_kcal",
                              "product_protein","product_carbs","product_fat",
                              "product_fiber","product_sugar","product_sodium",
                              "product_chol","Product_Diet_Tags","Product_Price_Category",
                              "created_at","updated_at")
        VALUES
          (1,'Flocons avoine',350,12.0,60.0,7.0,10.0,1.0,5.0,0.0,ARRAY['vegan','vegetarian'],'low',NOW(),NOW()),
          (2,'Blanc de poulet',165,31.0,0.0,3.6,0.0,0.0,75.0,85.0,ARRAY[]::text[],'medium',NOW(),NOW()),
          (3,'Lentilles cuites',116,9.0,20.0,0.4,7.9,1.8,2.0,0.0,ARRAY['vegan','vegetarian'],'low',NOW(),NOW()),
          (4,'Yaourt grec',100,10.0,4.0,0.7,0.0,4.0,46.0,5.0,ARRAY['vegetarian'],'medium',NOW(),NOW()),
          (5,'Saumon fume',142,20.0,0.0,6.8,0.0,0.0,700.0,40.0,ARRAY[]::text[],'high',NOW(),NOW()),
          (6,'Riz complet',111,2.6,23.0,0.9,1.8,0.4,1.0,0.0,ARRAY['vegan','vegetarian'],'low',NOW(),NOW()),
          (7,'Tofu ferme',144,15.0,2.2,9.0,0.3,0.5,15.0,0.0,ARRAY['vegan','vegetarian'],'medium',NOW(),NOW()),
          (8,'Amandes',579,21.0,22.0,50.0,12.5,4.0,1.0,0.0,ARRAY['vegan','vegetarian'],'medium',NOW(),NOW()),
          (9,'Oeuf entier',155,13.0,1.1,11.0,0.0,0.6,124.0,373.0,ARRAY['vegetarian'],'low',NOW(),NOW()),
          (10,'Banane',89,1.1,23.0,0.3,2.6,12.0,1.0,0.0,ARRAY['vegan','vegetarian'],'low',NOW(),NOW())
        ON CONFLICT ("Product_ID") DO NOTHING
    """))

    # ---------- Equipements ----------
    conn.execute(text("""
        INSERT INTO equipment ("Equipment_ID","Equipment_Name","Equipment_Category","Equipment_Location",
                               "created_at","updated_at")
        VALUES
          (1,'Halteres 10kg','weights','home',NOW(),NOW()),
          (2,'Tapis de yoga','flexibility','home',NOW(),NOW()),
          (3,'Barre de traction','weights','home',NOW(),NOW()),
          (4,'Corde a sauter','cardio','home',NOW(),NOW())
        ON CONFLICT ("Equipment_ID") DO NOTHING
    """))

    # ---------- User_Equipment ----------
    conn.execute(text("""
        INSERT INTO user_equipment ("User_ID","Equipment_ID")
        VALUES (2,1),(2,3),(1,2),(3,2),(3,4)
        ON CONFLICT DO NOTHING
    """))

    # ---------- Workout sessions ----------
    import datetime
    for i in range(15):
        day_offset = i * 2
        conn.execute(text("""
            INSERT INTO workout_sessions
              ("Session_ID","User_ID","Session_Date","Session_Duration",
               "Session_AvgBpm","Session_MaxBpm","Session_RestingBpm",
               "Session_Type","User_Feedback_Score","created_at","updated_at")
            VALUES (:sid,:uid,:dt,:dur,:bpm,:maxbpm,:rest,:stype,:fb,NOW(),NOW())
            ON CONFLICT ("Session_ID") DO NOTHING
        """), {
            "sid":    100 + i,
            "uid":    2,
            "dt":     datetime.date.today() - datetime.timedelta(days=day_offset),
            "dur":    45 + (i % 3) * 10,
            "bpm":    130 + (i % 5) * 5,
            "maxbpm": 160 + (i % 5) * 3,
            "rest":   55 + (i % 3) * 2,
            "stype":  ["strength", "cardio", "hiit"][i % 3],
            "fb":     3 + (i % 3),
        })

    # ---------- Biometrics ----------
    for i in range(5):
        conn.execute(text("""
            INSERT INTO biometrics_logs
              ("Log_ID","User_ID","Log_Date","Weight","Sleep_Hours","Heart_Rate",
               "created_at","updated_at")
            VALUES (:bid,:uid,:dt,:w,:sl,:hr,NOW(),NOW())
            ON CONFLICT ("Log_ID") DO NOTHING
        """), {
            "bid": 200 + i,
            "uid": 2,
            "dt":  datetime.date.today() - datetime.timedelta(days=i * 7),
            "w":   85.0 - i * 0.3,
            "sl":  7.5,
            "hr":  62 - i,
        })

print("Données de test insérées avec succès !")
print("  - 3 utilisateurs")
print("  - 10 produits")
print("  - 4 équipements")
print("  - 15 sessions workout (user 2)")
print("  - 5 logs biométriques (user 2)")
