import asyncio

from deep_coder.tui.app import DeepCodeApp


def test_app_has_timeline_and_composer_shell(fake_runtime, fake_project):
    async def run():
        app = DeepCodeApp(runtime=fake_runtime, project=fake_project)
        async with app.run_test(size=(120, 40)):
            assert app.query_one("#timeline")
            assert app.query_one("#status-strip")
            assert app.query_one("#composer")

    asyncio.run(run())


def test_session_switcher_lists_only_project_sessions(fake_runtime, fake_project):
    async def run():
        app = DeepCodeApp(runtime=fake_runtime, project=fake_project)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("ctrl+l")
            overlay = app.screen.query_one("#session-switcher")
            labels = [option.prompt for option in overlay.options]
            assert labels == [
                "session-a  make dir aa",
                "session-b  show history selector preview",
            ]

    asyncio.run(run())


def test_slash_opens_command_palette_and_filters_matches(fake_runtime, fake_project):
    async def run():
        app = DeepCodeApp(runtime=fake_runtime, project=fake_project)
        async with app.run_test(size=(120, 40)):
            composer = app.query_one("#composer")
            composer.text = "/"
            await app.run_action("refresh_command_palette")
            palette = app.query_one("#command-palette")
            labels = [option.prompt for option in palette.options]
            assert labels == ["/exit", "/history", "/model"]

            composer.text = "/hi"
            await app.run_action("refresh_command_palette")
            labels = [option.prompt for option in palette.options]
            assert labels == ["/history"]

    asyncio.run(run())


def test_tab_completes_selected_command(fake_runtime, fake_project):
    async def run():
        app = DeepCodeApp(runtime=fake_runtime, project=fake_project)
        async with app.run_test(size=(120, 40)) as pilot:
            composer = app.query_one("#composer")
            composer.text = "/hi"
            await app.run_action("refresh_command_palette")
            await pilot.press("tab")
            assert composer.text == "/history"

    asyncio.run(run())


def test_typing_slash_opens_command_palette(fake_runtime, fake_project):
    async def run():
        app = DeepCodeApp(runtime=fake_runtime, project=fake_project)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("/")
            await pilot.pause()
            palette = app.query_one("#command-palette")
            labels = [option.prompt for option in palette.options]
            assert labels == ["/exit", "/history", "/model"]
            assert palette.display is True

    asyncio.run(run())


def test_enter_selects_highlighted_command_without_tab(fake_runtime, fake_project):
    async def run():
        app = DeepCodeApp(runtime=fake_runtime, project=fake_project)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("/")
            await pilot.press("h")
            await pilot.press("enter")
            overlay = app.screen.query_one("#session-switcher")
            labels = [option.prompt for option in overlay.options]
            assert labels == [
                "session-a  make dir aa",
                "session-b  show history selector preview",
            ]

    asyncio.run(run())


def test_model_command_shows_model_choices_and_enter_applies_selection(fake_runtime, fake_project):
    async def run():
        app = DeepCodeApp(runtime=fake_runtime, project=fake_project)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("/")
            await pilot.press("m")
            await pilot.press("enter")
            composer = app.query_one("#composer")
            palette = app.query_one("#command-palette")
            labels = [option.prompt for option in palette.options]
            assert composer.text == "/model "
            assert labels == ["deepseek-chat", "deepseek-reasoner"]

            await pilot.press("down")
            await pilot.press("enter")
            status = str(app.query_one("#status-strip").renderable)
            assert app.runtime["config"].model_name == "deepseek-reasoner"
            assert "deepseek-reasoner" in status

    asyncio.run(run())


def test_escape_cancels_active_command_palette(fake_runtime, fake_project):
    async def run():
        app = DeepCodeApp(runtime=fake_runtime, project=fake_project)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("/")
            await pilot.press("m")
            await pilot.press("enter")
            composer = app.query_one("#composer")
            palette = app.query_one("#command-palette")
            assert composer.text == "/model "
            assert palette.display is True

            await pilot.press("escape")
            await pilot.pause()

            assert composer.text == ""
            assert palette.display is False

    asyncio.run(run())


def test_model_command_updates_runtime_and_status_strip(fake_runtime, fake_project):
    async def run():
        app = DeepCodeApp(runtime=fake_runtime, project=fake_project)
        async with app.run_test(size=(120, 40)) as pilot:
            composer = app.query_one("#composer")
            composer.text = "/model deepseek-reasoner"
            await app.run_action("refresh_command_palette")
            await pilot.press("enter")
            status = str(app.query_one("#status-strip").renderable)
            assert app.runtime["config"].model_name == "deepseek-reasoner"
            assert "deepseek-reasoner" in status

    asyncio.run(run())


def test_busy_command_shows_warning_in_status_strip(fake_runtime, fake_project):
    async def run():
        app = DeepCodeApp(runtime=fake_runtime, project=fake_project)
        async with app.run_test(size=(120, 40)) as pilot:
            app._turn_state = "running"
            app._update_status_strip()
            composer = app.query_one("#composer")
            composer.text = "/exit"
            await app.run_action("refresh_command_palette")
            await pilot.press("enter")
            status = str(app.query_one("#status-strip").renderable)
            assert "system now in runtime, please wait for the work end" in status

    asyncio.run(run())
