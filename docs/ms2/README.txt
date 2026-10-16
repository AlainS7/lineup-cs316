Line-up: A Fixed-Odds Sports Prediction Market
CompSci 316 Open Project - Milestone 2

Repository: https://github.com/AlainS7/lineup-cs316

Team members and progress since Milestone 1
--------------------------------------------
Since Milestone 1 the team agreed on the schema and page flow, and made a
first implementation of the site.

- Nathan Levine (Users role): Users table; registration with unique-email
  validation, login/logout; account page (profile edit, top up, withdraw,
  balance history); public profile page with record and net winnings;
  leaderboard.

- Dara Ajiboye (Markets role): Sports/Games/Lines tables; game browsing with
  sport filter, team and abbreviation search, upcoming/final toggle, sorting
  and pagination; hiding upcoming games with no open lines; game detail page;
  ESPN ingest job for schedules, scores and consensus lines, with unit tests
  against a recorded API fixture.

- Willow Rudge (Bet Slip role): persistent bet slip (CartItems) with
  add/remove/update stakes; odds arithmetic module; placing singles and
  parlays in one transaction with balance, open-line, started-game,
  duplicate-game and exposure checks, locking odds onto SlipLegs; bet
  history with status filter and bet detail page; settlement job that grades
  legs on final games, resolves slips and pays out; test suite.

- Alain Soto (Books role + shared infrastructure): GitHub repo and container
  setup; app factory, DB wrapper and CLI jobs; schema in db/create.sql and
  the seed-data generator; Books table and open-a-book flow; book dashboard
  with per-line exposure meters, pending counts and P&L; posting, editing,
  closing and deleting lines; LineExposure view and exposure-limit
  enforcement.

How to run
----------
See README.md in the repo. In short, inside the course container:
  pip3 install --user --break-system-packages -r requirements.txt
  flask db-init && ./lineup.sh
then open http://localhost:8080. Seed accounts use the password "password".
