from .doubles_game import DoublesGame
from .doubles_match import DoublesMatch
from .game import Game
from .guild_player import GuildPlayer
from .guild_setup import GuildSetup
from .guild_team import GuildTeam
from .match import Match
from .match_category import MatchCategory
from .participant import Participant
from .participant_team import ParticipantTeam
from .player import Player
from .settings import SsbuSettings
from .team import Team
from .tournament import Tournament
from .tournament_series import TournamentSeries


# original JSON-based data structure from Purah V1
old_data_structure = {
    'default_global': {
        'challonge_username': None,
        'challonge_api_key': None
    },
    'default_guild': {
        'participant_role_id': None,
        'organizer_role_id': None,
        'streamer_role_id': None,
        'matches_category_id': None,
        'starter_stages': [
            "Battlefield",
            "Final Destination",
            "Lylat Cruise",
            "Pokémon Stadium 2",
            "Smashville"
        ],
        'counterpick_stages': [
            "Yoshi's Story",
            "Kalos Pokémon League",
            "Town and City"
        ],
        'counterpick_bans': 2,
        'dsr': False
    },
    'default_member': {
        'challonge_id': None,
        'current_match_channel_id': None,
        'current_doubles_tournament_id': None,
        'current_team_member_id': None
    },
    'default_user': {
        'elo': 1000,
        'challonge_username': None,
        'challonge_user_id': None
    },
    'default_tournament': {
        'channel_id': None,
        'tournament_id': None,
        'guild_id': None,
        'signup_message_id': None,
        'checkin_message_id': None,
        'doubles': False
    },
    'default_participant': {
        'challonge_id': None,
        'tournament_id': None,
        'user_id': None,
        'guild_id': None,
        'starting_elo': None,
        'match_count': 0,
        'forfeit_count': 0
    },
    'default_team': {  # keys: lower user ID, higher user ID
        'player_1_user_id': None,
        'player_2_user_id': None,
        'name': None,
        'current_tournament_id': None,
        'current_participant_id': None,
        'elo': 1000
    },
    'default_participant_team': {  # key: challonge participant ID
        'challonge_id': None,
        'tournament_id': None,
        'guild_id': None,
        'player_1_user_id': None,
        'player_1_checked_in': False,
        'player_2_user_id': None,
        'player_2_checked_in': False,
        'starting_elo': None,
        'match_count': 0,
        'forfeit_count': 0
    },
    'default_match': {
        'match_id': None,
        'channel_id': None,
        'guild_id': None,
        'tournament_id': None,
        'player_1_user_id': None,
        'player_1_challonge_id': None,
        'player_2_user_id': None,
        'player_2_challonge_id': None,
        'player_1_score': 0,
        'player_2_score': 0,
        'current_game_nr': 1,
        'last_game_won_by': None,
        'wins_required': 2,
        'winner_user_id': None,
        'winner_challonge_id': None
    },
    'default_doubles_match': {
        'match_id': None,
        'channel_id': None,
        'guild_id': None,
        'tournament_id': None,
        'team_1_player_1_user_id': None,
        'team_1_player_2_user_id': None,
        'team_1_challonge_id': None,
        'team_2_player_1_user_id': None,
        'team_2_player_2_user_id': None,
        'team_2_challonge_id': None,
        'team_1_score': 0,
        'team_2_score': 0,
        'current_game_nr': 1,
        'last_game_won_by': None,
        'wins_required': 2,
        'winner_user_ids': None,
        'winner_challonge_id': None
    },
    'default_game': {
        'match_id': None,
        'game_number': None,
        'first_to_strike_user_id': None,
        'striking_message_id': None,
        'striked_stages': [],
        'suggested_stage': None,
        'suggested_by_user_id': None,
        'suggestion_accepted': None,
        'picked_stage': None,
        'winner_user_id': None,
        'needs_confirmation_by_user_id': None,
        'winner_confirmed': False
    }
}
