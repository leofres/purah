import hero
from hero import async_using_db


class SsbuController(hero.Controller):
    # TODO
    @async_using_db
    def get_stage(self, ctx, number):
        """Gets the stage with that number given the context

        Especially if stage striking is going on, this method
        is helpful to figure out which stage is currently being
        referred to.
        """
        # TODO check if match channel, then get stagelist
        # and get the stage from that (list index + 1),
        # else just instantiate a stage with the given number
        # and return that
        pass

    @async_using_db
    def get_starter_stages(self, ctx, channel=None):
        channel = channel or ctx.channel
        # TODO figure out if channel is tournament channel,
        # match channel or neither, then get stagelist
        # from tournament or guild
