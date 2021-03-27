import math

import hero


MU = 1500
PHI = 350
SIGMA = 0.06
TAU = 0.5
EPSILON = 0.000001
#: A constant which is used to standardize the logistic function to
#: `1/(1+exp(-x))` from `1/(1+10^(-r/400))`
Q = math.log(10) / 400


def _create_rating(mu, phi, sigma):
    return {
        'mu': mu,
        'phi': phi,
        'sigma': sigma
    }


class Glicko2:
    def __init__(self, mu=MU, phi=PHI, sigma=SIGMA):
        self.mu = mu
        self.phi = phi
        self.sigma = sigma

    @staticmethod
    def calculate_weight(my_score, other_score):
        _weight = my_score / (my_score + other_score)
        if _weight > 0.5:
            _weight = 1.0 - (1.0 - _weight) / 4.0
        return _weight

    def create_rating(self, mu=None, phi=None, sigma=None):
        if mu is None:
            mu = self.mu
        if phi is None:
            phi = self.phi
        if sigma is None:
            sigma = self.sigma
        return _create_rating(mu, phi, sigma)

    def scale_down(self, rating, ratio=173.7178):
        mu = (rating['mu'] - self.mu) / ratio
        phi = rating['phi'] / ratio
        return self.create_rating(mu, phi, rating['sigma'])

    def scale_up(self, rating, ratio=173.7178):
        mu = rating['mu'] * ratio + self.mu
        phi = rating['phi'] * ratio
        return self.create_rating(mu, phi, rating['sigma'])

    def reduce_impact(self, rating):
        """The original form is `g(RD)`. This function reduces the impact of
        games as a function of an opponent's RD.
        """
        return 1 / math.sqrt(1 + (3 * rating['phi'] ** 2) / (math.pi ** 2))

    def expect_score(self, rating, other_rating, impact):
        return 1. / (1 + math.exp(-impact * (rating['mu'] - other_rating['mu'])))

    def determine_sigma(self, rating, difference, variance):
        """Determines new sigma."""
        phi = rating['phi']
        difference_squared = difference ** 2
        # 1. Let a = ln(s^2), and define f(x)
        alpha = math.log(rating['sigma'] ** 2)
        def f(x):
            """This function is twice the conditional log-posterior density of
            phi, and is the optimality criterion.
            """
            tmp = phi ** 2 + variance + math.exp(x)
            a = math.exp(x) * (difference_squared - tmp) / (2 * tmp ** 2)
            b = (x - alpha) / (TAU ** 2)
            return a - b
        # 2. Set the initial values of the iterative algorithm.
        a = alpha
        if difference_squared > phi ** 2 + variance:
            b = math.log(difference_squared - phi ** 2 - variance)
        else:
            k = 1
            while f(alpha - k * math.sqrt(TAU ** 2)) < 0:
                k += 1
            b = alpha - k * math.sqrt(TAU ** 2)
        # 3. Let fA = f(A) and f(B) = f(B)
        f_a, f_b = f(a), f(b)
        # 4. While |B-A| > e, carry out the following steps.
        # (a) Let C = A + (A - B)fA / (fB-fA), and let fC = f(C).
        # (b) If fCfB < 0, then set A <- B and fA <- fB; otherwise, just set
        #     fA <- fA/2.
        # (c) Set B <- C and fB <- fC.
        # (d) Stop if |B-A| <= e. Repeat the above three steps otherwise.
        while abs(b - a) > EPSILON:
            c = a + (a - b) * f_a / (f_b - f_a)
            f_c = f(c)
            if f_c * f_b < 0:
                a, f_a = b, f_b
            else:
                f_a /= 2
            b, f_b = c, f_c
        # 5. Once |B-A| <= e, set s' <- e^(A/2)
        return math.exp(1) ** (a / 2)

    def rate(self, rating, series):
        # Step 2. For each player, convert the rating and RD's onto the
        #         Glicko-2 scale.
        rating = self.scale_down(rating)
        # Step 3. Compute the quantity v. This is the estimated variance of the
        #         team's/player's rating based only on game outcomes.
        # Step 4. Compute the quantity difference, the estimated improvement in
        #         rating by comparing the pre-period rating to the performance
        #         rating based only on game outcomes.
        d_square_inv = 0
        variance_inv = 0
        difference = 0
        if not series:
            # If the team didn't play in the series, do only Step 6
            phi_star = math.sqrt(rating['phi'] ** 2 + rating['sigma'] ** 2)
            return self.scale_up(self.create_rating(rating['mu'], phi_star, rating['sigma']))
        for actual_score, other_rating in series:
            other_rating = self.scale_down(other_rating)
            impact = self.reduce_impact(other_rating)
            expected_score = self.expect_score(rating, other_rating, impact)
            variance_inv += impact ** 2 * expected_score * (1 - expected_score)
            difference += impact * (actual_score - expected_score)
            d_square_inv += (
                expected_score * (1 - expected_score) *
                (Q ** 2) * (impact ** 2))
        difference /= variance_inv
        variance = 1. / variance_inv
        denom = rating['phi'] ** -2 + d_square_inv
        phi = math.sqrt(1 / denom)
        # Step 5. Determine the new value, sigma', ot the sigma. This
        #         computation requires iteration.
        sigma = self.determine_sigma(rating, difference, variance)
        # Step 6. Update the rating deviation to the new pre-rating period
        #         value, Phi*.
        phi_star = math.sqrt(phi ** 2 + sigma ** 2)
        # Step 7. Update the rating and RD to the new values, Mu' and Phi'.
        phi = 1 / math.sqrt(1 / phi_star ** 2 + 1 / variance)
        mu = rating['mu'] + phi ** 2 * (difference / variance)
        # Step 8. Convert ratings and RD's back to original scale.
        return self.scale_up(self.create_rating(mu, phi, sigma))

    def rate_match(self, rating_1, rating_2, score_1, score_2, series_1=None, series_2=None):
        if hero.TEST:
            series_1 = None
            series_2 = None
        weight_1 = self.calculate_weight(score_1, score_2)
        weight_2 = self.calculate_weight(score_2, score_1)
        if series_1 is None:
            series_1 = []
        if series_2 is None:
            series_2 = []
        return (
            self.rate(rating_1, series_1 + [(weight_1, rating_2)]),
            self.rate(rating_2, series_2 + [(weight_2, rating_1)])
        )

    def quality_1vs1(self, rating_1, rating_2):
        expected_score1 = self.expect_score(rating_1, rating_2, self.reduce_impact(rating_1))
        expected_score2 = self.expect_score(rating_2, rating_1, self.reduce_impact(rating_2))
        expected_score = (expected_score1 + expected_score2) / 2
        return 2 * (0.5 - abs(0.5 - expected_score))
