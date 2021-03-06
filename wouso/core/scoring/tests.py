from django.test import TestCase
from django.db.models.query import QuerySet
from django.contrib.auth.models import User
from wouso.core.game.models import Game
from wouso.core.scoring.models import Formula, Coin, History
from wouso.core.scoring import FormulaParsingError, setup_scoring, CORE_POINTS, check_setup, update_points
from wouso.core import scoring
from wouso.core.tests import WousoTest
from wouso.core.user.models import Player
from wouso.interface.activity import signals

class ScoringTestCase(TestCase):
    def setUp(self):
        self.user, new = User.objects.get_or_create(username='33')
        self.game = Game.get_instance()
        self.coin = Coin.objects.create(id='_test')

    def tearDown(self):
        #self.user.delete()
        self.game.delete()
        self.coin.delete()

    def testHistoryFor(self):
        no_history = scoring.history_for(self.user, self.game, external_id=999)
        self.assertEqual(len(no_history), 0 )

    def testScoreSimple(self):
        scoring.score_simple(self.user.get_profile(), self.coin, game=self.game, external_id=2, amount=10)
        multiple = scoring.history_for(self.user, self.game, external_id=2)

        self.assertTrue(isinstance(multiple, QuerySet))
        self.assertEqual(len(multiple), 1)

        history = list(multiple)[0]

        self.assertTrue(isinstance(history, History))
        self.assertEqual(history.amount, 10)

    def testCalculate(self):
        formula = Formula.objects.create(id='_test_formula',
            formula='_test=5', owner=self.game)

        # Call by name
        ret = scoring.calculate('_test_formula')
        self.assertTrue(isinstance(ret, dict))

        # Call by objcet
        ret = scoring.calculate(formula)
        self.assertTrue(isinstance(ret, dict))
        self.assertEqual(ret['_test'], 5)

        formula2 = Formula.objects.create(id='_test_formula2',
            formula='_test=5*3', owner=self.game)

        ret = scoring.calculate(formula2)
        self.assertTrue(isinstance(ret, dict))
        self.assertEqual(ret['_test'], 15)

        # Multiple coins
        formula2.formula='_test=5*3; points=4'

        ret = scoring.calculate(formula2)
        self.assertTrue(isinstance(ret, dict))
        self.assertEqual(ret['_test'], 15)
        self.assertEqual(ret['points'], 4)

        # Fail safe
        formula2.formula='_test=5*cucu'
        try:
            ret = scoring.calculate(formula2)
            # no error? wtf
            self.assertFalse(True)
        except Exception as e:
            self.assertTrue(isinstance(e, FormulaParsingError))

    def testScore(self):
        formula = Formula.objects.create(id='_test_formula_sc',
            formula='_test=13', owner=self.game)

        scoring.score(self.user.get_profile(), self.game, formula,
            external_id=3)

        hs = scoring.history_for(self.user, self.game, external_id=3)
        self.assertTrue(isinstance(hs, QuerySet))

        history = list(hs)[0]

        # check if specific coin has been updated
        self.assertEqual(history.coin, self.coin)
        self.assertEqual(history.amount, 13)


class UpdateScoringTest(WousoTest):
    def testUpdatePoints(self):
        Coin.add('points')
        Coin.add('gold')
        Formula.objects.create(id='level-gold', formula='gold=10*{level}', owner=None)
        player = self._get_player()
        player.points = 82
        player.level_no = 1
        player.save()
        update_points(player, None)
        coins = History.user_coins(player.user)
        self.assertIn('gold', coins)
        self.assertEqual(coins['gold'], 20)
        player.points = 10
        player.save()
        update_points(player, None)
        coins = History.user_coins(player.user)
        self.assertIn('gold', coins)
        self.assertEqual(coins['gold'], 0)


class ScoringHistoryTest(WousoTest):
    def test_user_coins(self):
        Coin.add('points')
        Coin.add('gold')
        player = self._get_player()
        self.assertIn('points', History.user_coins(player.user))

    def test_user_points(self):
        coin = Coin.add('points')
        player = self._get_player()

        scoring.score_simple(player, 'points', 10)

        up = History.user_points(player.user)
        self.assertTrue(up.has_key('wouso'))
        self.assertTrue(up['wouso'].has_key(coin))
        self.assertEqual(up['wouso'][coin], 10)

    def test_accessors(self):
        player = self._get_player()
        self.assertEqual(scoring.user_coins(player), scoring.user_coins(player.user))

    def test_sync_methods(self):
        player = self._get_player()
        coin = Coin.add('points')

        History.objects.create(user=player.user, coin=coin, amount=10)
        self.assertEqual(player.points, 0)
        scoring.sync_user(player)
        self.assertEqual(player.points, 10)

        History.objects.create(user=player.user, coin=coin, amount=10)
        self.assertEqual(player.points, 10)
        scoring.sync_all_user_points()
        player = Player.objects.get(pk=player.pk)
        self.assertEqual(player.points, 20)


class ScoringSetupTest(TestCase):
    def test_check_setup(self):
        self.assertFalse(check_setup())
        setup_scoring()
        self.assertTrue(check_setup())

    def test_setup(self):
        for c in CORE_POINTS:
            self.assertFalse(Coin.get(c))
        setup_scoring()
        for c in CORE_POINTS:
            self.assertTrue(Coin.get(c))

class ScoringFirstLogin(WousoTest):
    def test_first_login_points(self):
        f = Formula.add('start-points', formula='points=10')
        Coin.add('points')
        player = self._get_player()

        self.assertEqual(player.points, 0)

        # this won't work, since the activity is sent in our custom view
        #self.client.login(username=player.user.username, password='test')
        # using this instead
        signals.addActivity.send(sender=None, user_from=player, action="login", game = None, public=False)

        player = Player.objects.get(pk=player.pk)
        self.assertEqual(player.points, 10)
