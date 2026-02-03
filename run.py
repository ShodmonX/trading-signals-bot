from app.create_tables import criptos


print(",".join([cripto["symbol"] for cripto in criptos]))