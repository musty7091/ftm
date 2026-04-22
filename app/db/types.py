from sqlalchemy import Numeric


MONEY = Numeric(18, 2, asdecimal=True)
RATE = Numeric(18, 6, asdecimal=True)