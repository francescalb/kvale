from kvale.core.dmc import DmcColour, filter_dmc_colours, find_dmc_colour, load_dmc_colours


def test_bundled_colours_load() -> None:
    colours = load_dmc_colours()

    assert len(colours) == 454
    assert colours[0] == DmcColour("3713", "Salmon Very Light", 255, 226, 226)
    assert colours[0].hex_colour == "#ffe2e2"
    assert len({colour.number for colour in colours}) == len(colours)


def test_filter_matches_every_word_in_number_or_name() -> None:
    assert filter_dmc_colours("  ") == load_dmc_colours()
    salmon_light = filter_dmc_colours("SALMON light")
    assert salmon_light
    assert all("salmon" in c.name.casefold() and "light" in c.name.casefold() for c in salmon_light)
    assert [colour.number for colour in filter_dmc_colours("3713")] == ["3713"]
    assert filter_dmc_colours("no such colour") == ()


def test_find_by_screen_colour() -> None:
    found = find_dmc_colour("#FFE2E2")
    assert found is not None
    assert found.number == "3713"
    assert find_dmc_colour("#123457") is None
