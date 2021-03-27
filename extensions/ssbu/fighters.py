from discord.ext.commands import BadArgument


ALL_FIGHTERS = {
    1: "Mario",
    2: "Donkey Kong",
    3: "Link",
    4: "Samus",
    5: "Dark Samus",
    6: "Yoshi",
    7: "Kirby",
    8: "Fox",
    9: "Pikachu",
    10: "Luigi",
    11: "Ness",
    12: "Captain Falcon",
    13: "Jigglypuff",
    14: "Peach",
    15: "Daisy",
    16: "Bowser",
    17: "Ice Climbers",
    18: "Sheik",
    19: "Zelda",
    20: "Dr. Mario",
    21: "Pichu",
    22: "Falco",
    23: "Marth",
    24: "Lucina",
    25: "Young Link",
    26: "Ganondorf",
    27: "Mewtwo",
    28: "Roy",
    29: "Chrom",
    30: "Mr. Game & Watch",
    31: "Meta Knight",
    32: "Pit",
    33: "Dark Pit",
    34: "Zero Suit Samus",
    35: "Wario",
    36: "Snake",
    37: "Ike",
    38: "Pokémon Trainer",
    39: "Diddy Kong",
    40: "Lucas",
    41: "Sonic",
    42: "King Dedede",
    43: "Olimar",
    44: "Lucario",
    45: "R.O.B.",
    46: "Toon Link",
    47: "Wolf",
    48: "Villager",
    49: "Mega Man",
    50: "Wii Fit Trainer",
    51: "Rosalina & Luma",
    52: "Little Mac",
    53: "Greninja",
    54: "Mii Brawler",
    55: "Mii Swordfighter",
    56: "Mii Gunner",
    57: "Palutena",
    58: "Pac-Man",
    59: "Robin",
    60: "Shulk",
    61: "Bowser Jr.",
    62: "Duck Hunt",
    63: "Ryu",
    64: "Ken",
    65: "Cloud",
    66: "Corrin",
    67: "Bayonetta",
    68: "Inkling",
    69: "Ridley",
    70: "Simon",
    71: "Richter",
    72: "King K. Rool",
    73: "Isabelle",
    74: "Incineroar",
    75: "Piranha Plant",
    76: "Joker",
    77: "Hero",
    78: "Banjo & Kazooie",
    79: "Terry",
    80: "Byleth",
    81: "Min Min",
    82: "Steve",
    83: "Sephiroth",
}


FIGHTER_LOOKUP = {value: key for key, value in ALL_FIGHTERS.items()}


FIGHTER_ALIASES = {
    'M': 1,
    'DK': 2,
    'Yosh': 6,
    'Kirb': 7,
    'Poyo': 7,
    'Fox McCloud': 8,
    'Pika': 9,
    'Weegee': 10,
    'L': 10,
    'Falcon': 12,
    'Jigg': 13,
    'Jiggly': 13,
    'Puff': 13,
    'Princess Peach': 14,
    'Princess Daisy': 15,
    'King Koopa': 16,
    'Icies': 17,
    'Princess Zelda': 19,
    'Doc': 20,
    'Doctor Mario': 20,
    'Luci': 24,
    'YL': 25,
    'Ganon': 26,
    'Mew2': 27,
    'M2': 27,
    'Chrome': 29,
    'Game & Watch': 30,
    'Game and Watch': 30,
    'Game n Watch': 30,
    'Mr. Game and Watch': 30,
    'Mr. Game n Watch': 30,
    'Mr Game & Watch': 30,
    'Mr Game and Watch': 30,
    'Mr Game n Watch': 30,
    'Game&Watch': 30,
    'GamenWatch': 30,
    'G&W': 30,
    'GnW': 30,
    'GaW': 30,
    'GW': 30,
    'MK': 31,
    'MetaKnight': 31,
    'Pittoo': 33,
    'ZSS': 34,
    'Zero Suit': 34,
    'W': 35,
    'Snek': 36,
    'Solid Snake': 36,
    'PT': 38,
    'Trainer': 38,
    'Squirtle': 38,
    'Ivysaur': 38,
    'Charizard': 38,
    'Diddy': 39,
    'Sanic': 41,
    'Dedede': 42,
    'D3': 42,
    'Alph': 43,
    'Pikmin': 43,
    'Furry': 44,
    'ROB': 45,
    'Tink': 46,
    'TLink': 46,
    'Vill': 48,
    'MM': 49,
    'Mega': 49,
    'MegaMan': 49,
    'Wii Fit': 50,
    'WiiFit': 50,
    'WFT': 50,
    'WF': 50,
    'Wii': 50,
    'Rosalina': 51,
    'Rosa': 51,
    'Luma': 51,
    'Mac': 52,
    'LM': 52,
    'Gren': 53,
    'Brawler': 54,
    'Swordfighter': 55,
    'Swordie': 55,
    'Gunner': 56,
    'Palu': 57,
    'PacMan': 58,
    'Pac': 58,
    'Wobin': 59,
    'Bowser Jr': 61,
    'Koopaling': 61,
    'Koopalings': 61,
    'Larry': 61,
    'Wendy': 61,
    'Iggy': 61,
    'Morton': 61,
    'Lemmy': 61,
    'Ludwig': 61,
    'Duck Hunt Duo': 62,
    'Duck': 62,
    'DHD': 62,
    'DH': 62,
    'Cloud Strife': 65,
    'Bayo': 67,
    'Squid': 68,
    'Simon Belmont': 70,
    'Richter Belmont': 71,
    'Krool': 72,
    'King K Rool': 72,
    'K. Rool': 72,
    'K Rool': 72,
    'Isa': 73,
    'Incin': 74,
    'Plant': 75,
    'Plant Boi': 75,
    'Plant Boy': 75,
    'Piranha': 75,
    'Ren Amamiya': 76,
    'Ren': 76,
    'The Hero': 77,
    'Luminary': 77,
    'The Luminary': 77,
    'Erdrick': 77,
    'Solo': 77,
    'Eight': 77,
    'Banjo and Kazooie': 78,
    'Banjo n Kazooie': 78,
    'Banjo Kazooie': 78,
    'Banjo': 78,
    'Kazooie': 78,
    'B&K': 78,
    'BnK': 78,
    'BaK': 78,
    'Terry Bogart': 79,
    'MinMin': 81,
    'Alex': 82,
    'Zombie': 82,
    'Enderman': 82,
    'Ender Man': 82,
    'Seph': 83,
    'One-Winged Angel': 83,
}


FIGHTER_LOOKUP.update(FIGHTER_ALIASES)


# add lowercase and uppercase versions of fighter names and aliases
FIGHTER_LOOKUP.update({
    key.upper(): value for key, value in FIGHTER_LOOKUP.items() if not key.isupper()
})


FIGHTER_LOOKUP.update({
    key.lower(): value for key, value in FIGHTER_LOOKUP.items() if not key.islower()
})


class Fighter:
    def __init__(self, _id):
        if _id not in ALL_FIGHTERS:
            raise ValueError(f"Invalid Fighter ID: {_id}")
        self.id = _id

    @property
    def name(self):
        return ALL_FIGHTERS[self.id]

    @classmethod
    async def convert(cls, ctx, argument):
        try:
            return cls.parse(argument)
        except ValueError as ex:
            raise BadArgument(str(ex))

    @classmethod
    def parse(cls, argument):
        argument = str(argument)
        _argument = argument.lower()
        _argument = _argument.replace('’', "'")
        _argument = _argument.replace('pokemon', 'pokémon')
        try:
            _id = FIGHTER_LOOKUP[_argument]
        except KeyError:
            raise ValueError('"{}" is not a valid fighter.'.format(argument))
        return Fighter(_id)

    def __int__(self):
        return self.id

    def __str__(self):
        return self.name
