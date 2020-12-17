signup_message = """\
{intro_message}

The tournament starts {start_time}. The start time in your timezone, the bracket and \
other information can be found on the tournament's Challonge page: <{full_challonge_url}>

**To sign up for the tournament, simply click the {signup_emoji} below. \
You will have to check in before the tournament starts; check-in will start \
30 minutes before the tournament does.** Check-in will be as easy as signing up. \
You will also be role-pinged when check-in begins if you signed up.

__**Stagelist**__

**Starter Stages**

{starter_stages_list}

**Counterpick Stages**

{counterpick_stages_list}

Counterpick Bans: {counterpick_bans}
DSR: {dsr_on_off}

To prepare for the tournament, set up a ruleset according to these \
instructions: <https://imgur.com/a/yH7r5zJ>
"""

doubles_signup_message = """\
{intro_message}

The tournament starts {start_time}. The bracket and other information \
can be found on the tournament's Challonge page: <{full_challonge_url}>

**To sign up for the tournament, simply use `{prefix}teamup @user` to team up with \
someone else, then click the {signup_emoji} below. \
You will have to check in before the tournament starts; check-in will start \
30 minutes before the tournament does.** Check-in will be as easy as signing up. \
You will also be pinged when check-in begins if you signed up; this ping will \
bypass your notification settings for this server.

__**Stagelist**__

**Starter Stages**

{starter_stages_list}

**Counterpick Stages**

{counterpick_stages_list}

Counterpick Bans: {counterpick_bans}
DSR: {dsr_on_off}

To prepare for the tournament, set up a ruleset according to these \
instructions: <https://imgur.com/a/yH7r5zJ>
"""

description = """\
{intro_message}

To join the tournament, visit our Discord server \
( {invite_link} ), open the #{channel.name} channel \
and click on the check mark. The rest is explained on Discord. \
We're using a new system we built to innovate tournament management. \
We hope you'll like it!

__**Stagelist**__

**Starter Stages**

{starter_stages_list}

**Counterpick Stages**

{counterpick_stages_list}

Counterpick Bans: {counterpick_bans}
DSR: {dsr_on_off}
"""

checkin_message = """\
{role.mention} Check-in has begun! Click the {checkin_emoji} if you're ready \
to participate in the tournament that starts in 30 minutes!
"""

doubles_checkin_message = """\
{role.mention} Check-in has begun! Click the {checkin_emoji} if you're ready \
to participate in the tournament that starts in 30 minutes! \
**Both team members have to check in for the team to be able to \
enter the tournament!**
"""

teamup_request = """\
{partner.mention}, {author.mention} would like to team up with you \
for doubles tournaments! Click the \u2705 to accept, \
or the \u274E to reject.
"""

tournament_start = """The tournament has started! Please wait while I create \
the match channel for your first match. Participants can talk in this channel now.
"""

match_intro = """\
{match_title} between {player_1.mention} and {player_2.mention} (Best of {best_of_number})

**{player_1.display_name}**, please create the arena unless {player_2.display_name} \
has already created one and you are fine with them hosting the arena.

You can forfeit using `.forfeit`, which will make you lose this match.
I have determined randomly who will start striking stages.
"""

match_intro_factions = """\
{match_title} between {player_1.mention} ({player_1_faction}) \
and {player_2.mention} ({player_2_faction}) \
(Best of {best_of_number})

**{player_1.display_name}**, please create the arena unless {player_2.display_name} \
has already created one and you are fine with them hosting the arena.

You can forfeit using `.forfeit`, which will make you lose this match.
I have determined randomly who will start striking stages.
"""

first_striking = """{member.mention}, please pick a stage you would like \
to strike (type `.strike <stage number>`, replacing `<stage number>` \
with the number of the stage you want to strike, example: `.strike 2` \
would strike Final Destination):

{stages}

Note: You can try to skip the striking process once per game by \
directly suggesting a stage using `.pick <stage number>`. \
If your opponent accepts your suggestion, you will play the game \
on the stage you suggested.
"""

second_striking = """\
{member.mention}, please select a stage that you want to strike
(use `.strike <stage number>`):

{stages}
"""

third_striking = """\
{member.mention}, please choose another stage to strike:

{stages}
"""

fourth_striking = """\
{member.mention}, please strike one final stage:

{stages}
"""

second_striking_second_game = third_striking

stage_suggestion = """\
{suggested_to.mention}, {suggested_by.display_name} suggested the stage **{stage}**. \
To accept this stage and skip the rest of the striking procedure for this match, \
type `.accept`; to reject the suggestion and continue striking, type `.reject`.
"""

suggestion_rejected = """\
{suggested_by.mention}, your stage suggestion was rejected.
"""

picking_stage = """\
{member.mention}, please pick the stage for this game \
(must be one that hasn't been striked, use `.pick <stage number>`):

{stages}
"""

picking_battlefield_version = """\
{member.mention}, please announce which Battlefield version you \
want to play on if you don't want to play on Battlefield. \
You may **not** pick one of these Battlefield versions:

{forbidden_versions}

If you choose Mementos, make sure to agree on a track as well.
"""

picking_omega_version = """\
{member.mention}, please announce which \U000003a9 version you \
want to play on if you don't want to play on Final Destination. \
You may **not** pick one of these \U000003a9 versions:

{forbidden_versions}

If you choose Mementos, make sure to agree on a track as well.
"""

start_first_game = """\
**Game 1 between {player_1.mention} and {player_2.mention}**

Stage: **{stage}**

You may now start the game on the given stage. When the game is over, report \
the winner as follows: The winner sends `.won` or the loser sends `.lost`, \
then the opponent confirms using `.lost` / `.won`. GLHF!
"""

start_game = """\
**Game {current_game_nr} between {player_1.mention} and {player_2.mention}**

Stage: **{stage}**

If you won, type `.won`, if you lost, type `.lost`.
"""

confirm_lost = """\
{loser.mention}, please confirm that {winner.display_name} won the game by typing `.lost`.
"""

confirm_won = """\
{winner.mention}, please confirm that you won the game by typing `.won`.
"""

who_won_current_game = """\
**{winner.display_name}** takes game {game_nr}!
"""

who_won_final_game = """\
**{winner.display_name}** takes game {game_nr} and wins the match with \
a score of {player_1_score}-{player_2_score}!

This channel will be closed in 1 minute.
"""

# this one will be used only by the setwinner command
who_won_match = """\
**{winner.display_name}** wins the match!

This channel will be closed in 1 minute.
"""

forfeited_match = """\
**{loser.display_name}** forfeited, which means \
**{winner.display_name}** wins the match!

This channel will be closed in 1 minute.
"""

disqualified_win = """\
**{disqualified.display_name}** was disqualified, which means \
**{winner.display_name}** wins the match!

This channel will be closed in 1 minute.
"""

participant_faction_results = """\
Your rank in **{tournament.name}** is **{rank}**!

{faction} Points: {faction_points_change} -> {total_faction_points}
{currency}: {credits_change} -> {total_balance}
ELO: {elo_change} -> {new_elo}
"""

participant_results = """\
Your rank in **{tournament.name}** is **{rank}**!

ELO: {elo_change} -> {new_elo}
"""

participant_doubles_results = """\
Your team's rank in **{tournament.name}** is **{rank}**!

Team ELO: {elo_change} -> {new_elo}
"""

factions_tournament_end = """\
{name} has ended! Thank you for your participation. Here are the rankings:

{top_8}

And here are the results for this Worlds Collide tournament:

Light: **{light}**
Darkness: **{darkness}**
Subspace: **{subspace}**

You can view the entire ranking and bracket on: {challonge_url}
You should receive a message about the faction points and \

This channel will be read-only in 10 minutes.
"""

tournament_end = """\
{name} has ended! Thank you for your participation. Here are the rankings:

{top_8}

You can view the entire ranking and bracket on: {challonge_url}
This channel will be read-only in 10 minutes.
"""
