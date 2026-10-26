from dataclasses import dataclass


@dataclass(frozen=True)
class Service:
    id: str
    name: str
    minutes: int
    price: int


SERVICES = {
    "haircut": Service("haircut", "Classic Haircut", 30, 1800),
    "beard": Service("beard", "Beard Trim", 20, 900),
    "combo": Service("combo", "Haircut + Beard", 50, 2500),
}
# One chair, Monday–Saturday 10:00–19:00. Sunday closed. Prices in synthetic PKR.
OPEN_HOUR = 10
CLOSE_HOUR = 19
BUSINESS_INFO = (
    "Northline Studio offers Classic Haircut (30 minutes, PKR 1,800), Beard Trim "
    "(20 minutes, PKR 900), and Haircut + Beard (50 minutes, PKR 2,500). "
    "We open Monday through Saturday, 10 AM to 7 PM, and close on Sunday. "
    "Our fictional address is 12 Example Lane. All appointments use the studio timezone."
)
