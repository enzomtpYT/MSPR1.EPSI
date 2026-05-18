from sqlalchemy import create_engine, text

url = "postgresql://postgres:postgres@localhost:5432/mspr_db"
try:
    engine = create_engine(url)
    with engine.connect() as conn:
        tables = conn.execute(
            text("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")
        ).fetchall()
        print("Connexion PostgreSQL OK")
        print("Tables trouvees :")
        for t in tables:
            print(" -", t[0])

        users    = conn.execute(text('SELECT COUNT(*) FROM users')).scalar()
        products = conn.execute(text('SELECT COUNT(*) FROM products')).scalar()
        ws       = conn.execute(text('SELECT COUNT(*) FROM workout_sessions')).scalar()
        ml       = conn.execute(text('SELECT COUNT(*) FROM meal_logs')).scalar()
        bio      = conn.execute(text('SELECT COUNT(*) FROM biometrics_logs')).scalar()
        print(f"\nUtilisateurs     : {users}")
        print(f"Produits         : {products}")
        print(f"Workout sessions : {ws}")
        print(f"Meal logs        : {ml}")
        print(f"Biometrics logs  : {bio}")
except Exception as e:
    print(f"ERREUR : {e}")
