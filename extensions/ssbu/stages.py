from discord import PartialEmoji
from discord.ext.commands import BadArgument

from hero.utils import async_using_db, async_to_sync
from hero import models

from . import models as ssbu_models


ALL_STAGES = {
    1: "Battlefield",
    2: "Small Battlefield",
    3: "Big Battlefield",
    4: "Final Destination",
    5: "Peach's Castle",
    6: "Kongo Jungle",
    7: "Hyrule Castle",
    8: "Super Happy Tree",
    9: "Dream Land",
    10: "Saffron City",
    11: "Mushroom Kingdom",
    12: "Princess Peach's Castle",
    13: "Rainbow Cruise",
    14: "Kongo Falls",
    15: "Jungle Japes",
    16: "Great Bay",
    17: "Temple",
    18: "Brinstar",
    19: "Yoshi's Island (Melee)",
    20: "Yoshi's Story",
    21: "Fountain of Dreams",
    22: "Green Greens",
    23: "Corneria",
    24: "Venom",
    25: "Pokémon Stadium",
    26: "Onett",
    27: "Mushroom Kingdom II",
    28: "Brinstar Depths",
    29: "Big Blue",
    30: "Fourside",
    31: "Delfino Plaza",
    32: "Mushroomy Kingdom",
    33: "Figure-8 Circuit",
    34: "WarioWare, Inc.",
    35: "Bridge of Eldin",
    36: "Norfair",
    37: "Frigate Orpheon",
    38: "Yoshi's Island",
    39: "Halberd",
    40: "Lylat Cruise",
    41: "Pokémon Stadium 2",
    42: "Port Town Aero Dive",
    43: "Castle Siege",
    44: "Distant Planet",
    45: "Smashville",
    46: "New Pork City",
    47: "Summit",
    48: "Skyworld",
    49: "Shadow Moses Island",
    50: "Luigi's Mansion",
    51: "Pirate Ship",
    52: "Spear Pillar",
    53: "75m",
    54: "Mario Bros.",
    55: "Hanenbow",
    56: "Green Hill Zone",
    57: "3D Land",
    58: "Golden Plains",
    59: "Paper Mario",
    60: "Gerudo Valley",
    61: "Spirit Train",
    62: "Dream Land GB",
    63: "Unova Pokémon League",
    64: "Prism Tower",
    65: "Mute City SNES",
    66: "Magicant",
    67: "Arena Ferox",
    68: "Reset Bomb Forest",
    69: "Tortimer Island",
    70: "Balloon Fight",
    71: "Living Room",
    72: "Find Mii",
    73: "Tomodachi Life",
    74: "PictoChat 2",
    75: "Mushroom Kingdom U",
    76: "Mario Galaxy",
    77: "Mario Circuit",
    78: "Skyloft",
    79: "The Great Cave Offensive",
    80: "Kalos Pokémon League",
    81: "Coliseum",
    82: "Flat Zone X",
    83: "Palutena's Temple",
    84: "Gamer",
    85: "Garden of Hope",
    86: "Town and City",
    87: "Wii Fit Studio",
    88: "Boxing Ring",
    89: "Gaur Plain",
    90: "Duck Hunt",
    91: "Wrecking Crew",
    92: "Pilotwings",
    93: "Wuhu Island",
    94: "Windy Hill Zone",
    95: "Wily Castle",
    96: "Pac-Land",
    97: "Super Mario Maker",
    98: "Suzaku Castle",
    99: "Midgar",
    100: "Umbra Clock Tower",
    101: "New Donk City Hall",
    102: "Great Plateau Tower",
    103: "Moray Towers",
    104: "Dracula's Castle",
    105: "Mementos",
    106: "Yggdrasil's Altar",
    107: "Spiral Mountain",
    108: "King of Fighters Stadium",
    109: "Garreg Mach Monastery",
    110: "Spring Stadium",
    111: "Minecraft World",
}





STAGE_LOOKUP = {value: key for key, value in ALL_STAGES.items()}


STAGE_ALIASES = {
    'BF': 1,
    'SBF': 2,
    'Small BF': 2,
    'SmallBF': 2,
    'FD': 4,
    'Final': 4,
    'Omega': 4,
    'YS': 20,
    'Story': 20,
    'Lylat': 40,
    'PS2': 41,
    'Stadium': 41,
    'SV': 45,
    'Ville': 45,
    'Kalos': 80,
    'TaC': 86,
    'T&C': 86,
    'Town': 86,
    # TODO
}


STAGE_LOOKUP.update(STAGE_ALIASES)

# add lowercase and uppercase versions of stage names and aliases
STAGE_LOOKUP.update({
    key.upper(): value for key, value in STAGE_LOOKUP.items() if not key.isupper()
})


STAGE_LOOKUP.update({
    key.lower(): value for key, value in STAGE_LOOKUP.items() if not key.islower()
})

# A stage is legal if it is Tier 3 or better:
# https://www.ssbwiki.com/Stage_legality#Stage_legality_in_Super_Smash_Bros._Ultimate
LEGAL_STAGES = [
    1,  # Battlefield
    2,  # Small Battlefield
    4,  # Final Destination
    20,  # Yoshi's Story
    25,  # Pokémon Stadium
    34,  # WarioWare, Inc.
    38,  # Yoshi's Island
    40,  # Lylat Cruise
    41,  # Pokémon Stadium 2
    45,  # Smashville
    63,  # Unova Pokémon League
    78,  # Skyloft
    80,  # Kalos Pokémon League
    86,  # Town and City
    106,  # Yggdrasil's Altar
]


DEFAULT_STARTER_STAGES = [
    1,  # Battlefield
    4,  # Final Destination
    41,  # Pokémon Stadium 2
    45,  # Smashville
    86,  # Town and City
]


DEFAULT_COUNTERPICK_STAGES = [
    2,  # Small Battlefield
    19,  # Yoshi's Story
    80,  # Kalos Pokémon League
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
            print(f"Invalid stage: {argument}")
            raise BadArgument(str(ex))
        except TypeError:
            return await cls.get_stage_from_number(ctx, int(argument))

    @classmethod
    @async_using_db
    def get_stage_from_number(cls, ctx, number):
        """Gets the stage with that number given the context

        Especially if stage striking is going on, this method
        is helpful to figure out which stage is currently being
        referred to. This is not needed and not called if the
        stage is being referred to with its name or an alias.
        """
        # check if match channel, then get stagelist
        channel = async_to_sync(models.TextChannel.from_discord_obj(ctx.channel))
        try:
            match = ssbu_models.Match.get(channel=channel)
        except ssbu_models.Match.DoesNotExist:
            return Stage(number)
        # and get the stage from that (list index + 1),
        starter_stages = match.tournament.ruleset.starter_stages
        counterpick_stages = match.tournament.ruleset.counterpick_stages
        stages = starter_stages + counterpick_stages
        return Stage(stages[number - 1])

    @classmethod
    def parse(cls, argument):
        try:
            _id = int(argument)
            # make this fail so we can handle stage numbers in strike commands and such
        except ValueError:
            print(f"Actually parsing {argument}")
            print(list(STAGE_LOOKUP.keys()))
            argument = str(argument)
            try:
                _id = STAGE_LOOKUP[argument]
            except KeyError:
                raise ValueError('"{}" is not a valid stage.'.format(argument))
        else:
            raise TypeError("Cannot parse Stage from 'int'.")
        return Stage(_id)

    @classmethod
    def serialize(cls, stage):
        return str(int(stage))

    @classmethod
    def get_default_starters(cls):
        return [cls(stage_id) for stage_id in DEFAULT_STARTER_STAGES]

    @classmethod
    def get_default_counterpicks(cls):
        return [cls(stage_id) for stage_id in DEFAULT_COUNTERPICK_STAGES]

    def __int__(self):
        return self.id

    def __str__(self):
        return self.name
