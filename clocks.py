from wasabi2d import clock


ui = clock.default_clock
game = ui.create_sub_clock()
coro = game.coro
animate = game.animate

del clock
