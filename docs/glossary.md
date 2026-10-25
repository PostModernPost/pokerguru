# Glossary

Plain-language meanings of the poker words used in the app. Definitions only, no strategy.
The app underlines these words; tap one for its meaning. Edit `web/glossary.json` and run
`python scripts/export_glossary.py` to update this file.

## The games

- **6-max**: A table with at most six players. Positions: UTG, HJ, CO, BTN, SB, BB.
- **9-handed** *(also: full ring)*: A table with nine players. Positions: UTG, UTG1, UTG2, LJ, HJ, CO, BTN, SB, BB.
- **cash game** *(also: cash)*: A game where chips are worth real money at face value and you can leave whenever you like. Compare tournament.
- **heads-up**: Two players only. Heads-up, the small blind is also the button and acts first before the flop.
- **Hold'em** *(also: Texas Hold'em, NLHE, No-Limit Hold'em)*: The most common poker game. Each player gets two private cards (hole cards) and shares five community cards (the board). Your hand is the best five cards out of those seven. 'No-Limit' means you may bet any amount up to your whole stack.
- **no-limit**: A betting rule: you may bet or raise any amount up to all your chips.
- **Omaha** *(also: PLO, Pot-Limit Omaha)*: Like Hold'em but you get four hole cards and must use exactly two of them plus exactly three board cards. 'Pot-Limit' means the most you can bet or raise is the size of the pot.
- **pot-limit**: A betting rule: the largest bet or raise you may make is the size of the pot after you call. The Pot limit drill practises that calculation.
- **tournament** *(also: MTT)*: Everyone buys in for the same amount, the blinds go up over time, and you play until one player has all the chips. Prizes are paid by finishing place, so chips are not worth exactly their face value (see ICM).

## Positions and blinds

- **ante**: A small forced bet from every player (or from one player on everyone's behalf) before the deal, common in tournaments. It makes the pot bigger before anyone acts.
- **big blind** *(also: BB)*: The seat two left of the button. It posts a forced bet before the deal, and stack sizes and bets in this app are measured in big blinds. '10bb' means ten big blinds.
- **blinds**: The two forced bets (small blind and big blind) posted before each hand so there's something to play for.
- **button** *(also: BTN, dealer)*: The seat with the dealer marker. It acts last on every street after the flop. The button moves one seat left after each hand.
- **CO** *(also: cutoff)*: 'Cutoff': the seat just right of the button.
- **hero**: You, the player whose decision is being drilled.
- **HJ** *(also: hijack)*: 'Hijack': the seat two to the right of the button.
- **LJ** *(also: lojack)*: 'Lojack': the seat three to the right of the button, used at 9-handed tables.
- **position**: Where you sit relative to the dealer button, which decides when you act. Acting later is called having position; you see what others do first.
- **small blind** *(also: SB)*: The seat just left of the button. It must put in a forced bet (half a big blind here) before the cards are dealt.
- **UTG** *(also: under the gun, UTG1, UTG2)*: 'Under the gun': the first seat to act before the flop, just left of the big blind. At a 9-handed table the next two seats are UTG1 and UTG2.
- **villain**: Any opponent. 'Villain bets 10' just means an opponent bet 10; it isn't personal.

## The deal and the streets

- **board** *(also: community cards)*: The face-up shared cards in the middle: three on the flop, one more on the turn, one more on the river.
- **flop**: The first three board cards, dealt together, and the betting round that follows.
- **hole cards** *(also: hand)*: Your private cards: two in Hold'em, four in Omaha.
- **postflop**: Everything after the flop is dealt: the flop, turn and river betting rounds.
- **preflop**: The first betting round, after you get your hole cards and before any board cards are dealt.
- **river**: The fifth and last board card and its betting round. After it, remaining players show their hands.
- **runout**: The board cards still to come. 'Any runout' means whatever the remaining cards turn out to be.
- **showdown**: The end of the hand, when the remaining players reveal their cards and the best hand wins the pot.
- **street**: A betting round. The four streets are preflop, flop, turn and river.
- **turn**: The fourth board card and its betting round.

## Actions

- **3-bet** *(also: three-bet, 3-bets)*: A re-raise: the second raise in a betting round. Preflop, the big blind counts as the first bet, the open as the second, so the re-raise is the third, hence '3-bet'.
- **4-bet** *(also: four-bet, 4-bets)*: A re-raise of a 3-bet: the third raise in the round.
- **all-in** *(also: shove, shoves, push, jam, allin)*: Bet every chip you have. 'Shove', 'push' and 'jam' all mean the same thing.
- **bet**: Put chips in when nobody has yet this round. Later players must call, raise or fold.
- **call**: Match the current bet to stay in the hand.
- **check**: Pass the action without betting, allowed only when nobody has bet yet this round.
- **fold**: Give up your hand and any chips you've already put in. You can't win the pot.
- **folded to you** *(also: folded to)*: Everyone who acted before you folded, so you're the first with a real decision.
- **limp** *(also: limps)*: Just call the big blind preflop instead of raising.
- **raise**: Increase the bet. 'Raise to 7' means your total bet this round becomes 7, not 7 more on top.
- **raise first in** *(also: RFI, open, open-raise, opens)*: Being the first player to put money in voluntarily, with a raise, after everyone before you folded. Also called opening the pot.
- **to call** *(also: amount to call)*: How many more chips you need to put in to match the current bet.

## Hands and cards

- **blocker** *(also: blocks, block)*: A card in your hand that makes certain opponent hands impossible or less likely. Holding the ace of spades means nobody else can have the ace-high spade flush.
- **board plays** *(also: the board plays)*: In Hold'em, when the best five cards are the five on the board, so everyone still in has the same hand. This never applies in Omaha because of the two-hole-cards rule.
- **broadway** *(also: broadways)*: Any of the cards ten through ace. A 'broadway straight' is ten-jack-queen-king-ace, the highest straight.
- **connector** *(also: connectors, suited connector)*: Two cards next to each other in rank, like 9-8. 'Suited connector' means they also share a suit.
- **draw** *(also: drawing, draws)*: A hand that isn't much yet but becomes strong if the right card comes, like four cards to a flush.
- **hand class** *(also: AKs, AKo, hand classes)*: Shorthand for a type of starting hand, ignoring exact suits. 'AKs' is ace-king suited (same suit), 'AKo' is ace-king offsuit, 'TT' is a pair of tens. T means ten. There are 169 classes in Hold'em.
- **hand rankings** *(also: straight flush, four of a kind, full house, flush, straight, three of a kind, two pair, one pair, high card)*: From best to worst: straight flush (five in a row, same suit; ace-high is a royal flush), four of a kind, full house (three of one rank plus a pair), flush (five of one suit), straight (five in a row), three of a kind, two pair, one pair, high card.
- **kicker**: A card that doesn't make the hand itself but breaks ties. With a pair of aces, your other card is the kicker.
- **nut draw** *(also: drawing to the nuts)*: A draw that, if it gets there, makes the best possible hand. A 'non-nut draw' would make a strong hand that could still lose to a better one.
- **offsuit**: Two cards of different suits, written with an 'o' (A5o).
- **outs** *(also: out)*: The cards still in the deck that would improve your hand to the one you're hoping for. Four cards to a flush have nine outs.
- **pocket pair** *(also: pair, pairs)*: Two hole cards of the same rank, like 8-8.
- **suited**: Two cards of the same suit, written with an 's' (A5s). Suited hands can make flushes more easily.
- **the nuts** *(also: nuts, nut, nut hand)*: The best possible hand given the cards on the board. In this app it also takes your own cards into account: a hand nobody else can hold because you hold its cards doesn't count.
- **two hole cards rule** *(also: exactly two hole cards)*: The Omaha rule: your final hand must use exactly two of your four hole cards and exactly three board cards. A flush on the board is not your flush unless you hold two of that suit.
- **wheel**: The lowest straight: ace-2-3-4-5, where the ace counts as a one.

## Math and odds

- **direct odds**: Pot odds counting only the chips already in the pot and the bet you face, nothing you might win later. The Equity drill uses direct odds only.
- **equity**: Your share of the pot if the hand were played out many times from here: a 40% equity means you'd win about 40% of the time (ties count half). It's a fact about the cards, not a decision.
- **EV** *(also: expected value, chip EV)*: Expected value: the average result of a decision if you made it many times. 'Chip EV' measures it in chips, treating every chip as equal.
- **exploitability**: How much, per hand, a perfect opponent could gain against a strategy. Zero means the strategy can't be beaten in the long run (an equilibrium).
- **ICM**: Independent Chip Model: a way of valuing tournament chips in prize money rather than at face value, because finishing places pay out unevenly. Not used in this app yet; the push/fold charts are chip EV.
- **implied odds**: Extra chips you might win on later streets if your draw gets there. The Equity drill ignores these on purpose, and says so.
- **indifferent** *(also: indifference)*: When two actions have the same expected value, so it doesn't matter which you pick. Charts often mix such hands, playing them one way some of the time.
- **Monte Carlo** *(also: simulated hands, simulation)*: Estimating a probability by running the situation many times with random cards and counting the results. The app deals 2,500 random runouts to estimate equity, accurate to about one percentage point.
- **Nash equilibrium** *(also: equilibrium, Nash)*: A pair of strategies where neither player can do better by changing only their own. The push/fold charts are an equilibrium: the shoving and calling ranges are each the best reply to the other.
- **pot odds**: The price you're being offered: how much you must call compared with what's in the pot. If the pot is 100 and you must call 50, you're risking 50 to win 150.
- **required equity** *(also: equity needed, need)*: The break-even point for a call: call / (pot + bet + call). If your equity is at least this, calling at least breaks even on this street. The app computes it for you.

## Ranges and charts

- **card removal**: The fact that cards you hold can't be in anyone else's hand, which changes how likely each opponent hand is. The solver accounts for it.
- **chart** *(also: charts)*: A table saying what to do with each starting hand in one specific situation (position, table size, stack depth, what happened before you). The Preflop drill grades you against one.
- **computed**: An answer the program worked out mathematically (equity, pot-limit sizes, push/fold ranges) rather than looked up in a chart someone wrote.
- **facing** *(also: facing an open, facing a 3-bet, facing a shove)*: What's been done to you before you act: an open means someone raised, a 3-bet means someone re-raised your raise, a shove means someone went all-in.
- **frequency** *(also: frequencies, mixed strategy, mixed)*: How often a chart takes an action with a hand. '60% raise, 40% fold' means the hand is a raise most of the time but not always. Mixed hands are usually ones that are close to indifferent.
- **push/fold** *(also: push or fold, shove or fold)*: Playing a short stack with only two choices preflop: all-in or fold. The tournament charts in this app cover that for heads-up play.
- **range**: All the hands a player could have in a situation, usually drawn as a 13-by-13 grid of the 169 hand classes. 'A tight range' means few hands; 'a wide range' means many.
- **sample chart** *(also: SAMPLE)*: A fake chart with random numbers, used only to build and test the app. Red banner, not real strategy, don't learn from it.
- **source** *(also: chart source)*: Where a chart's numbers came from. Every chart in this app says, so you know what you're learning from.
- **spot** *(also: spots, spot type)*: One decision point: the game, positions, stack sizes and action so far. 'Spot type' groups them: raise first in, facing an open, facing a 3-bet, push or fold, facing a shove.
- **stack depth** *(also: stack, stacks, effective stack, bb deep)*: How many big blinds a player has. '100bb deep' is a normal cash-game stack; under 15bb is short. With two players the smaller stack is what matters (the effective stack).

## The app

- **acceptable** *(also: close enough)*: Grade for a mixed hand where the chart takes your action between 15% and 50% of the time, or for an equity answer within two points of the line. Not wrong, not the main line.
- **correct**: Grade for choosing an action the chart takes at least 50% of the time (or the exact answer in a math drill).
- **drill my leaks** *(also: leak drill)*: A Preflop mode that serves only your weak areas and due reviews.
- **hand category** *(also: hand categories)*: A group of starting hands used in the stats: pairs, suited aces, offsuit aces, suited broadways, offsuit broadways, suited connectors, other suited, other offsuit.
- **leak** *(also: leaks)*: A kind of spot you consistently get wrong. Here: a position, spot type or hand category you've answered at least five times with a score under 70%.
- **review** *(also: due for review, reviews)*: A specific spot you missed earlier that the app brings back after a few more hands, then at growing intervals, until you get it right repeatedly (spaced repetition).
- **spaced repetition**: A learning method: things you got wrong come back soon, things you got right come back later and later. The app counts the gaps in hands played rather than days.
- **wrong**: Grade for an action the chart takes under 15% of the time, or an incorrect answer in a math drill.
