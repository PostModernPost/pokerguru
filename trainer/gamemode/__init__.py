"""Game mode: a continuous simulated cash game with feedback on your decisions.

PokerKit runs the hands (dealing, betting rules, pots, showdown). The bots play
the verified preflop charts and a simple strength-and-odds policy after the flop;
they keep the game moving and are not a model of good play. Feedback comes from
the same answer keys as the drills wherever one exists, and says so when none does.
"""
