Postmortem
==========

PyWeek 32 has been a blast, and I wanted to sketch down some thoughts on how
it went.

For me, PyWeek is both a creative outlet and the opportunity to try out and
advance new technology. But it has been quite a while since I last competed in
PyWeek: the last PyWeek I entered was PyWeek 28, almost exactly 2 years ago.

I've not been idle in that time; I've worked on all kinds of game engine things.
My PyWeek entry Axium has been the opportunity to put all of that into practice.
It felt very good to be able to take advantage of years of investment.

I'm going to walk through some of those things:


Joystick support in Pygame 2
----------------------------

In summer 2020 I fixed all the joystick support in Pygame 2.0 to work with SDL2.
Apart from some extra methods like the ability to get the battery state of a
joystick, there are two fundamental improvements:

* For each controller you can get a GUID which identifies the device, and which
  you can look up in the
  [GameControllerDB](https://github.com/gabomdq/SDL_GameControllerDB/) to find
  button mappings (e.g. which button number is the 'A' button).

* Joysticks can be attached and detached after the game has started, which
  fires `JOYDEVICEADDED`/`JOYDEVICEREMOVED` events. This just feels like an
  essential capability of game controllers now. Restarting the game when you
  plug in a joystick seems like something from the 1990s. My gamepads are
  bluetooth and don't stay connected - the experience you expect is that you
  start them and after they buzz to signal that they are connected, you
  immediately see them in the game.


wasabigeom.vec2
---------------

For the 10 years that I have been doing PyWeek I have struggled to find a vector
class that I actually love. So I wrote one, and it works fine. I had zero
problems with it.

The most fundamental thing a vector class needs in Python is to be immutable.
There are dozens of reasons. For example, if you want a vector `@property`
with a setter then you want it to always be triggered when the vector is
changed. If the vector is mutable if can be mutated without triggering the
setter.

Another case is default parameters. It's very well known that [you should not
use mutable default arguments](https://docs.python-guide.org/writing/gotchas/#mutable-default-arguments).
If your vector class is mutable and you use it as a default argument you have
every possibility of falling foul of this, perhaps with something as innocuous
as a `+=` operator. A similar situation arises for constants and class
variables.

The second thing that a vector class needs, for game dev, is to be fast. If the
vector is immutable - and it must be - then you are creating new ones often. And
games use a lot of vector maths; slow vector operations can really slow
everything down.

The third thing it needs is to be Pythonic. It's harder to say what this means
but obvious things are that it duck-types like a namedtuple, supports operator
overloading, has a repr that looks like code. Some vector classes that you get
out of libraries like Box2D, for example, follow different conventions
established by the underlying C or C++ library.

The fourth thing is that it should deal with angles in radians. Degrees are
fine for beginners but eventually you will want to do some complex trigonometry
where the factors of π/180 become a nuisance. That's the point at which
you give up on degrees and just use radians for the rest of your life. Degrees
become a user interface thing, not something you use in code.

So in September 2020, I wrote `wasabigeom.vec2`, and it just works. It's
immutable, Pythonic, and uses radians.

I also [ran benchmarks](https://github.com/lordmauve/wasabi2d/issues/17) which
indicate it has best-in-class performance. It is faster than tuples,
`pygame.math.Vector2`, numpy, and faster than I could make it in Rust. The main
reason for this is that Cython makes it very easy to
[add a freelist](https://cython.readthedocs.io/en/latest/src/userguide/extension_types.html#fast-instantiation)
which reduces the need for memory allocations in realistic Python code.

Using `vec2` throughout my game just became something I could take for granted.
Vector maths without papercuts.


pyfxr
-----
Most of the sound effects for my game were created with
[pyfxr](https://github.com/lordmauve/pyfxr), a library and a GUI that I created
in early 2021.

I've used [sfxr](https://www.drpetter.se/project_sfxr.html),
[bfxr](https://www.bfxr.net/), and [jsfxr](https://sfxr.me/) for generating
sound effects for PyWeek entries for years.

pyfxr implements the same sound generation code for Python, in fast Cython code.
So in some respects it is no different, except that I can pip install it. And I
can include the sound effects by pasting code rather than writing out .wav
files.

But because pyfxr has an API I can programmatically vary some of the parameters.

So, picking up star bits in Axium plays tinkle noises with random pitches,
which is quite satisfying.


Wasabi2D
--------

Mostly, features in Wasabi2D worked as intended. I shook out quite a few bugs
during the week of development, in everything from text rendering to tile maps.

One big feature I added was allowing multiple viewports in one window. They
can be separate scenes or different camera views onto the same scene. It wasn't
as hard to do this as I feared, and the benefits were greater: it meant that I
could create a whole new scene as the "HUD" layer which doesn't move with the
camera from the main scene.

Unfortunately I can imagine wanting to do post-processing effects that combine
viewports, which this model can't satisfy. I think the model is stretched too
far and it needs a complete rethink for Wasabi2D 2.x. Probably more along the
lines of composing exactly the render pipeline you want. The drawbacks of that
are more effort to get a simple game off the ground quickly (which is a strong
capability in Wasabi2D today).

But the most important feature of Wasabi2D deserves a whole section:


Coroutines
----------

My first real exposure to coroutines in games was from
[Scratch](https://scratch.mit.edu), which I only really encountered through
Pygame Zero and my work in education. Scratch is a block-based programming
environment for young children.

Scratch has a [forever loop](https://en.scratch-wiki.info/wiki/Forever_(block))
which is quite a bit different to `while True:` in Python. If you wrap code in
a forever block you see the updates from each loop. After a small amount
of experimentation you get the sense that it actually corresponds to Python code
like `while await next_frame()`, or perhaps more nicely written with an async
iterable: `async for _ in frames()`.

Scratch hides the yield points, but that's fine - so does gevent. They're still
coroutines. But Scratch makes the point really clearly: you write simple code
controlling each object and those code blocks run at the same time to form a
game.

Python has language support for `async` and `await` keywords so we can just do
the same thing, more explicitly. How does that work out?

Well, great. This comes up all the time. You often want to chain a bunch of
animations:

```python
await appear()
await move_to(10, 10)
await sleep(0.3)
await disappear()
```

The rest of the game has to keep running while these execute. At least, the
game engine has to redraw the screen, but it might also want to respond to
input. The `await` keyword allows the function to be suspended and for other
things to happen while an operation works and before the function resumes. It is
annoying to write the same chaining in any other way; that's why this capability
is in the language. Note that `await` is only allowed inside functions defined
with `async def`.

`await` isn't the only construct you can use in an `async def`. For example, you
could also loop once each frame:

```python
async for frame_time in frames():
    ...
```

That would be a strong enough use case to justify the use coroutines. And that
was where coroutines stood in Wasabi2D at the end of 2019.

But I got the opportunity to study with Nathaniel Smith, author of Trio, on the
topic of structured concurrency.

I can't really describe the concept of structured concurrency better than
[Nathaniel's blogpost](https://vorpus.org/blog/notes-on-structured-concurrency-or-go-statement-considered-harmful/).

In short the structured concurrency pattern I implemented in Wasabi2D looks like
this:

```python
ship = scene.layers[0].add_sprite('ship')
async with w2d.Nursery() as ns:
    ns.do(drive_ship())
    ns.do(shoot())
    ns.do(effects.trail(ship, color='blue'))
```

A nursery allows a set of tasks that are allowed to run concurrently. You can
add tasks at any point. But all tasks must complete before the code
continues after the `async with` block. This means you can put code afterwards:

```python
async def play_life():
    ship = scene.layers[0].add_sprite('ship')
    async with w2d.Nursery() as ns:
        ship.nursery = ns
        ns.do(drive_ship())
        ns.do(shoot())
        ns.do(effects.trail(ship, color='blue'))
    ship.delete()
    await explode(ship.pos)
```

Actually I want to always delete the ship sprite even if an exception happens,
so in fact let's write

```python
async def play_life():
    ship = scene.layers[0].add_sprite('ship')
    try:
        async with w2d.Nursery() as ns:
            ship.nursery = ns
            ns.do(drive_ship(ship))
            ns.do(shoot(ship))
            ns.do(effects.trail(ship, color='blue'))
    finally:
        ship.delete()
    await explode(ship.pos)
```

Now the three tasks I spawn in that nursery are infinite loops (with `awaits`).
So the only way that nursery is exiting is if it is *cancelled* with
`nursery.cancel()`. Cancelling the nursery aborts all the tasks in it (and any
awaits inside the `async with` block too).

Cancelling raises a `Cancelled` exception inside the task, which unwinds its
stack; this cancels any nurseries inside that task too! So there are two paths
through this code:

* `ship.nursery` is cancelled. This means that flow continues after the nursery,
  the ship is deleted, and the explosion is shown.
* Some outer nursery is cancelled. This means that flow doesn't continue - the
  exception propagates, and only `ship.delete()` is executed.

The cool thing is that I don't have to worry too much about either of those
paths. The nursery is the life of the ship; the `play_life()` function is the
*lifecycle* of the ship. Context managers and finally blocks help to
automatically clean up the state of the game when things die or exit. All this
works incredibly well.

Why have separate drive and shoot tasks? The answer for that is that it's really
elegant to define a shoot task that limits the rate of fire to one bullet every
0.1 seconds:

```python
async def shoot(ship):
    while True:
        await controller.button_press('a')
        game_nursery.do(bullet(ship.pos, ship.angle))
        await sleep(0.1)
```

That demonstrates another cool feature: you can await Pygame events in any
coroutine. `controller.button_press()` provides a few layers of abstraction
around that to filter for events related to this joystick and button:

```python
async def button_press(self, *buttons):
    while True:
        ev = await w2d.next_event(pygame.JOYBUTTONDOWN)
        if ev.instance_id != self.id:
            continue
        button = self.device_mapping.get(ev.button)
        if not buttons or button in buttons:
            return button
```

(Quite an expensive way to filter events but it works.)

What I think this shows, is that coroutines are an excellent tool to model
independent processes in a game. The "shoot" coroutine is an obvious loop,
shoot on button press, wait before allowing the next press, do that until
cancelled.

I've written this loop many times without coroutines and it never drops out in
as little code. Plus there are classic pitfalls like you allow shooting while
dead. This is impossible in the structured concurrency world. You no longer need
to track object states. The state of an object is encoded in the structure of
code. At every yield point in a coroutine you know the state of the object it
belongs to.

There's one other thing I'll mention, which is that classic concurrency problems
show up between coroutines. Axium has a building that spawns repair drones which
are issued through an iris door. There's one iris, many drones, and the iris
takes a moment to open and close. I used Event objects to synchronise access
to the door. The door is operated by
[its own task](https://github.com/lordmauve/axium/blob/09007a0e08684119f3b327a0fbc9f73cdd1fde5b/building.py#L673)
and there is a coroutine
[`await open_iris()`](https://github.com/lordmauve/axium/blob/09007a0e08684119f3b327a0fbc9f73cdd1fde5b/building.py#L667)
that both requests the iris to open (if not already open) and waits for that to
happen. Just two event objects are enough to synchronise this, and it works
beautifully. I think that if I had written this without coroutines I would have
taken much longer to debug it, and it would basically *contain* the
implementation of an Event object (a flag and a list of things that are waiting
for the flag). Event objects are a re-usable version of a type of
concurrency that shows up in games anyway! By using coroutines we're able to
extract it and make it re-usable.
