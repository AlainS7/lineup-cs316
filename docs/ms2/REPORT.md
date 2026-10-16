# Line-up — Milestone 2 Report

## Changes to the proposal

The architecture is unchanged: Users, Markets (Games and Lines), Bet Slip, and
Books map onto the Mini-Amazon Users, Products, Cart/Order, and Sellers roles.
Though there are two refinements since the proposal. First, we chose ESPN's
public scoreboard API as the sports data source; it needs no key and returns
schedules, final scores, and a consensus point spread and total for each game,
which lets the ingest job post real lines as well as settle them. Second, we
defined a book's exposure on a line precisely, which was the sum, over pending
slips containing that line, of potential payout minus stake. Parlays attribute
their full liability to every leg, which is conservative but simple to enforce
and explain.

## Features and goals

**Basic (weights sum to 100):**

1. **Accounts (15).** Register with a unique email, log in/out, edit profile and
   password, top up and withdraw a virtual balance, view balance history, public
   profile with record and net winnings.
2. **Browsing markets (15).** List upcoming games filtered by sport, searched by
   team, sorted by time or line count; game page showing every book's moneyline,
   spread, and total with exposure meters; public book pages.
3. **Bet slip and parlays (25).** Persistent slip across sessions; add/remove
   lines and change stakes; place as singles or as a parlay (2+ legs, distinct
   games) with combined odds shown; placement is one transaction that locks
   odds, checks balance, closed lines, started games, and exposure.
4. **Settlement (20).** Scheduled job joins pending legs with final games,
   grades moneyline/spread/total including pushes, resolves slips, pays winners,
   voids dead parlay legs; bet history shows locked odds and results.
5. **Books and exposure limits (15).** Any user can open a book, post and edit
   lines, set per-line exposure limits; dashboard shows liability per line and
   P&L; bets that would breach a limit are rejected.
6. **Live data (10).** `flask ingest` pulls real games, scores, and consensus
   lines from ESPN into the house book.

**Bonus:**

1. **Leaderboard and analytics (weight 2).** Public ranking by net winnings;
   per-book trend charts of handle and exposure over time.
2. **Live odds movement (weight 3).** Re-price house lines from the API before
   kickoff and show line history on the game page; locked odds remain fixed.
3. **Scheduled automation (weight 1).** Run ingest and settle from cron inside
   the container with a status page showing last run times.

## Progress so far

The repo, Flask app, and schema (`db/create.sql`: Users, Sports, Games, Books,
Lines, CartItems, BetSlips, SlipLegs, BalanceTransactions, plus a `LineExposure`
view) are complete and seeded with sample games, lines, and bets. All basic
features above have a first working implementation: accounts, browsing, slip
with singles and parlays, settlement (a set-based `UPDATE ... FROM` grades legs,
then slips are resolved and paid), book dashboard with exposure limits, and the
ESPN ingest job. A pytest suite covers the odds math and an end-to-end flow
(register, bet, hit the exposure limit, settle, get paid). All SQL uses
parameterized `text()` queries.

## Remaining tasks

Build the larger test database for Milestone 4 from several weeks of ingested
games. Add pagination to the game list. Polish the UI and error messages. Record
each member's Milestone 3 endpoint demo. Implement bonus features in priority
order. Write documentation and the final report.

## How we used LLMs

We used an LLM to turn our agreed design into the first implementation/prototype
of the schema, routes, and templates, to draft the settlement SQL and the
seed-data generator, and help writing the test suite. We reviewed and ran
everything ourselves, and design decisions (schema, exposure definition, parlay
rules, data source) were made by the team.
