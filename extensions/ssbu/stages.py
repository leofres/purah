from discord.ext.commands import BadArgument


ALL_STAGES = {
    1: "Battlefield",
    2: "Big Battlefield",
    3: "Final Destination",
    4: "Peach's Castle",
    5: "Kongo Jungle",
    6: "Hyrule Castle",
    7: "Super Happy Tree",
    8: "Dream Land",
    9: "Saffron City",
    10: "Mushroom Kingdom",
    11: "Princess Peach's Castle",
    12: "Rainbow Cruise",
    13: "Kongo Falls",
    14: "Jungle Japes",
    15: "Great Bay",
    16: "Temple",
    17: "Brinstar",
    18: "Yoshi's Island (Melee)",
    19: "Yoshi's Story",
    20: "Fountain of Dreams",
    21: "Green Greens",
    22: "Corneria",
    23: "Venom",
    24: "Pokémon Stadium",
    25: "Onett",
    26: "Mushroom Kingdom II",
    27: "Brinstar Depths",
    28: "Big Blue",
    29: "Fourside",
    30: "Delfino Plaza",
    31: "Mushroomy Kingdom",
    32: "Figure-8 Circuit",
    33: "WarioWare, Inc.",
    34: "Bridge of Eldin",
    35: "Norfair",
    36: "Frigate Orpheon",
    37: "Yoshi's Island",
    38: "Halberd",
    39: "Lylat Cruise",
    40: "Pokémon Stadium 2",
    41: "Port Town Aero Dive",
    42: "Castle Siege",
    43: "Distant Planet",
    44: "Smashville",
    45: "New Pork City",
    46: "Summit",
    47: "Skyworld",
    48: "Shadow Moses Island",
    49: "Luigi's Mansion",
    50: "Pirate Ship",
    51: "Spear Pillar",
    52: "75m",
    53: "Mario Bros.",
    54: "Hanenbow",
    55: "Green Hill Zone",
    56: "3D Land",
    57: "Golden Plains",
    58: "Paper Mario",
    59: "Gerudo Valley",
    60: "Spirit Train",
    61: "Dream Land GB",
    62: "Unova Pokémon League",
    63: "Prism Tower",
    64: "Mute City SNES",
    65: "Magicant",
    66: "Arena Ferox",
    67: "Reset Bomb Forest",
    68: "Tortimer Island",
    69: "Balloon Fight",
    70: "Living Room",
    71: "Find Mii",
    72: "Tomodachi Life",
    73: "PictoChat 2",
    74: "Mushroom Kingdom U",
    75: "Mario Galaxy",
    76: "Mario Circuit",
    77: "Skyloft",
    78: "The Great Cave Offensive",
    79: "Kalos Pokémon League",
    80: "Coliseum",
    81: "Flat Zone X",
    82: "Palutena's Temple",
    83: "Gamer",
    84: "Garden of Hope",
    85: "Town and City",
    86: "Wii Fit Studio",
    87: "Boxing Ring",
    88: "Gaur Plain",
    89: "Duck Hunt",
    90: "Wrecking Crew",
    91: "Pilotwings",
    92: "Wuhu Island",
    93: "Windy Hill Zone",
    94: "Wily Castle",
    95: "Pac-Land",
    96: "Super Mario Maker",
    97: "Suzaku Castle",
    98: "Midgar",
    99: "Umbra Clock Tower",
    100: "New Donk City Hall",
    101: "Great Plateau Tower",
    102: "Moray Towers",
    103: "Dracula's Castle",
    104: "Mementos",
    105: "Yggdrasil's Altar",
    106: "Spiral Mountain",
    107: "King of Fighters Stadium",
    108: "Garreg Mach Monastery",
}


STAGE_LOOKUP = {value: key for key, value in ALL_STAGES.items()}


STAGE_ALIASES = {
    'bf': 1,
    'fd': 3,
    # TODO
}


STAGE_LOOKUP.update(STAGE_ALIASES)

# add lowercase and uppercase versions of stage names and aliases
STAGE_LOOKUP.update({
    key: value.upper() for key, value in STAGE_LOOKUP.items() if not value.isupper()
})


STAGE_LOOKUP.update({
    key: value.lower() for key, value in STAGE_LOOKUP.items() if not value.isupper() and not value.islower()
})

# A stage is legal if it is Tier 3 or better:
# https://www.ssbwiki.com/Stage_legality#Stage_legality_in_Super_Smash_Bros._Ultimate
LEGAL_STAGES = [
    1,  # Battlefield
    3,  # Final Destination
    19,  # Yoshi's Story
    24,  # Pokémon Stadium
    33,  # WarioWare, Inc.
    37,  # Yoshi's Island
    39,  # Lylat Cruise
    40,  # Pokémon Stadium 2
    44,  # Smashville
    62,  # Unova Pokémon League
    77,  # Skyloft
    79,  # Kalos Pokémon League
    85,  # Town and City
    105,  # Yggdrasil's Altar
]


DEFAULT_STARTER_STAGES = [
    1,  # Battlefield
    3,  # Final Destination
    40,  # Pokémon Stadium 2
    44,  # Smashville
    85,  # Town and City
]


DEFAULT_COUNTERPICK_STAGES = [
    19,  # Yoshi's Story
    37,  # Yoshi's Island
    39,  # Lylat Cruise
    62,  # Unova Pokémon League
    79,  # Kalos Pokémon League
]


BANNED_FORMS = {  # ID, Reason for ban
    20: "Framerate issues",
    54: "2D",
    61: "2D",
    64: "2D",
    81: "2D",
    83: "Camera Issues",
    89: "2D",
    91: "Camera Issues",
    93: "Grass covers objects",
    95: "2D",
    96: "2D",
    108: "Slightly lowered ceiling",
}


def generate_banned_forms_list():
    _tmp = [f"{ALL_STAGES[key]} ({value})" for key, value in BANNED_FORMS]
    return '\n'.join(_tmp)


class Stage:
    def __init__(self, _id):
        if _id not in ALL_STAGES:
            raise ValueError("Invalid Stage ID.")
        self.id = _id

    @property
    def name(self):
        return ALL_STAGES[self.id]

    @property
    def is_legal(self):
        return self.id in LEGAL_STAGES

    @classmethod
    async def convert(cls, ctx, argument):
        try:
            return cls.parse(argument)
        except ValueError as ex:
            raise BadArgument(str(ex))
        except TypeError:
            ssbu = ctx.bot.get_controller('ssbu')
            await ssbu.get_stage(ctx, int(argument))

    @classmethod
    def parse(cls, argument):
        try:
            _id = int(argument)
        except TypeError:
            argument = str(argument)
            try:
                _id = STAGE_LOOKUP[argument]
            except KeyError:
                raise ValueError('"{}" is not a valid fighter.'.format(argument))
        else:
            raise TypeError("Cannot parse Fighter from 'int'.")
        return Stage(_id)

    def __int__(self):
        return self.id

    def __str__(self):
        return self.name
