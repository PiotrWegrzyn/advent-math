import secrets

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Student

CODE_LENGTH = 6

NICKS = """
Kasztan Pierniczek Bombka Sopelek Renifer Bałwanek Śnieżka Choinka Gwiazdka Pierożek Makowiec Barszczyk
Opłatek Sanki Łyżwa Mandarynka Cynamon Imbir Lukier Orzeszek Szyszka Jemioła Kolędnik Elfik Skrzat
Dzwoneczek Puchacz Wiewiórka Jeżyk Borsuk Żołądź Ziemniaczek Kluska Pączek Rogalik Kompocik Kakao
Czekoladka Marcepan Karmelek Sernik Kremówka Budyń Galaretka Kisiel Rodzynek Migdał Pistacja Kokos
Ananas Kiwi Śliwka Gruszka Jabłuszko Malinka Jagódka Truskawka Borówka Żurawina Brokuł Rzodkiewka
Marchewka Pietruszka Koperek Fasolka Groszek Kalarepa Dynia Cukinia Papryczka Pomidorek Pingwin Foka
Mors Lisek Zajączek Sowa Gil Sikorka Wróbelek Bocian Żubr Łoś Chomik Alpaka Lama Panda Koala Pancernik
Kangur Żyrafa Hipcio Słonik Tygrysek Kapibara Ośmiornica Meduza Krewetka Rozgwiazda Delfinek Śledzik
Kijanka Żabka Ślimak Biedronka Trzmiel Świetlik Mrówka Motylek Kometa Meteor Planeta Księżyc Rakieta
Satelita Kompas Lizak Bączek Latawiec Klocek Kredka Gumka Temperówka Cyrkiel Linijka Kątomierz
Kalkulator Liczydło Ułamek Pierwiastek Trójkąt Kwadracik Sześcian Piramida Walec Stożek Ekierka
""".split()


def new_code(session: Session) -> str:
    while True:
        code = "".join(secrets.choice("0123456789") for _ in range(CODE_LENGTH))
        if session.scalar(select(Student.id).where(Student.code == code)) is None:
            return code


def new_nick(session: Session) -> str:
    taken = set(session.scalars(select(Student.nick)))
    free = [nick for nick in NICKS if nick not in taken]
    if free:
        return secrets.choice(free)
    suffix = 2
    while True:
        free = [f"{nick} {suffix}" for nick in NICKS if f"{nick} {suffix}" not in taken]
        if free:
            return secrets.choice(free)
        suffix += 1


def normalize_code(raw: str) -> str:
    return "".join(ch for ch in raw if ch.isdigit())
