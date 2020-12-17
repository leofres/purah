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
}


FIGHTER_LOOKUP = {value: key for key, value in ALL_FIGHTERS.items()}


FIGHTER_ALIASES = {
    'M': 1,
    'DK': 2,
    'Kirb': 7,
    'Fox McCloud': 8,
    'Pika': 9,
    'Weegee': 10,
    'Falcon': 12,
    'Jigg': 13,
    'Jiggly': 13,
    'Puff': 13,
    'Princess Peach': 14,
    'Princess Daisy': 15,
    'King Koopa': 16,
    'Icies': 17,
    'Princess Zelda': 19,
    # TODO
}


FIGHTER_LOOKUP.update(FIGHTER_ALIASES)


# add lowercase and uppercase versions of fighter names and aliases
FIGHTER_LOOKUP.update({
    key.upper(): value for key, value in FIGHTER_LOOKUP.items() if not key.isupper()
})


FIGHTER_LOOKUP.update({
    key.lower(): value for key, value in FIGHTER_LOOKUP.items() if not key.isupper() and not key.islower()
})


class Fighter:
    def __init__(self, _id):
        if _id not in ALL_FIGHTERS:
            raise ValueError("Invalid Fighter ID.")
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
        try:
            _id = FIGHTER_LOOKUP[argument]
        except KeyError:
            raise ValueError('"{}" is not a valid fighter.'.format(argument))
        return Fighter(_id)

    def __int__(self):
        return self.id

    def __str__(self):
        return self.name
