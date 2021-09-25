# Axium

Humanity's expansion into space had lasted centuries by the time we encountered
the vicious Threx.

The Threx adopted a single, religious mission: destroy all alien life and
technology.

At the edge of the Axium system, you have a chance to make your stand. Build
structures to assist you in fighting off the Threx.


## Controls

Control is by joystick or gamepad. If you don't have a gamepad to hand, remember
that Xbox, Switch, and Playstation controllers can all be paired to a PC. If you
would like to invest in a gamepad, the [8bitdo](https://www.8bitdo.com/)
controllers are very good.

* Left stick: move
* A (bottom button): shoot
* B (right button): boost
* Y (top button): build mode
* Left/Right Shoulder: select building
* Start: begin game/pause

Axium reads the
[Game Controller DB file](https://github.com/gabomdq/SDL_GameControllerDB)
which provides mappings for a large number of controllers so that they behave
approximately the same (despite different layouts and button orderings). I don't
have direct experience of how comprehensive this is, but you can add mappings
using the instructions in that repo.


## Co-op

Connect a second controller to play co-op. The second player can join at any
time by pressing start.

The players share the lives and credit balance.


## Buildings

* Reactor - fusion reactors provide power for up to 3 base buildings. If you
  lose your reactors your buildings will still work, but you will not be able
  to build more.

* Phaser Pod - after a few moments work, generates two phaser packs that charge
  your shot. Phaser shots will travel through multiple enemies.

* Rocket Arsenal - generates a single rocket pack. Rockets home onto targets.

* Repair Bay - hosts a swarm of drones that repair your base structures. Drones
  cannot attack the Threx and are destroyed if theor repair bay is destroyed.


## Install and run

Install all requirements from `requirements.txt`.

To run, type

    python axium.py


## Credits

Space Background: By Mink Mingle
https://unsplash.com/photos/NORa8-4ohA0

Font: Sector 34 by Neoqueto
https://www.dafont.com/sector-034.font?l[]=10&l[]=1


Music: For Robots Friendly Floater Mix (remixed by Rico Zerone) by Tom Woxom
https://freemusicarchive.org/music/Tom_Woxom/Robot/11_-_For_Robots_Friendly_Floater_Mix_remixed_by_Rico_Zerone
