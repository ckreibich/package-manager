import abc
import argparse
import re
import sys
import threading
from collections.abc import Callable
from typing import Any, TextIO

# A type for the kind of callable we use for activities:
# they return an error string upon completion.
UiCallable = Callable[..., str]


class Activity(abc.ABC):
    """An activity conducted by zkg, such as a package install, build, or
    package source refresh.
    """

    def __init__(self) -> None:
        # An error message to leave in case the activity didn't complete
        # successfully.
        self.error = ""

    @abc.abstractmethod
    def __call__(self) -> None:
        pass


class CallableActivity(Activity):
    """An activity defined by a callable passed on to us."""

    def __init__(self, call: UiCallable):
        super().__init__()
        self.call = call

    def __call__(self) -> None:
        self.error = self.call()


class ProgressActivity(Activity):
    """An activity for which progress is quantifiable."""

    def __init__(self, total: float = 1.0) -> None:
        super().__init__()
        self.total = total

    @abc.abstractmethod
    def __call__(self) -> None:
        pass

    def progress(self, delta: float) -> None:
        """Callback invoked by the activity as it unfolds, whenever it can
        report progress toward completion.
        """
        pass


class Worker(threading.Thread):
    """A worker executes an activity. It runs in the background (in the sense of
    Python's threading model, so not truly concurrently), and can be waited
    upon.
    """

    def __init__(
        self,
        activity: Activity,
    ) -> None:
        super().__init__()
        self.activity = activity

    def run(self) -> None:
        """Runs the activity in the background."""
        self.activity()

    def wait(
        self,
        out: TextIO | Any = sys.stdout,
    ) -> None:
        """Blocks until this activity ends, optionally writing liveness indicators.

        This never returns until this thread dies (i.e., is_alive() is False).
        When an output file object is provided, the method also indicates
        progress by writing a dot character to it once per second. This happens
        only when the file is a TTY. When a message is given, it gets written
        out first, regardless of TTY status. Any output always terminates with a
        newline.

        Args:
            msg (str): a message to write first.

            out (file-like object): the destination to write to.

        """
        is_tty = hasattr(out, "isatty") and out.isatty()

        while True:
            self.join(1.0)
            if not self.is_alive():
                break

            if out is not None and is_tty:
                out.write(".")
                out.flush()

        if out is not None and is_tty:
            out.write("\n")
            out.flush()


class Markup:
    """A markup instance groups rules of content substitions.

    These content substitutions will usually apply color markup but can also
    contain other transformations.
    """

    class Rule:
        """A Rule instance captures a single content-rewriting rule."""

        def __init__(
            self,
            open_in: str,
            open_out: str,
            close_in: str | None = "",
            close_out: str | None = "",
        ) -> None:
            """Rule constructor.

            Each rule knows how to translate a pair of opening and closing tags.
            For example, "[zkg.pkg]" and "[/zkg.pkg]" can be translated
            specifically via such a rule.  The closing-tag substitution is
            optional and skipped if passed in as None.

            When the input/output closing tags are the empty string, and the
            opening tags are rich-style tags of the form "[...]", the
            constructor infers the closing tags from the opening ones.
            """
            self.open_in = open_in
            self.open_out = open_out
            self.close_in = close_in
            self.close_out = close_out

            # None means closing tags don't apply to this rule.
            if self.close_in is None:
                return
            if self.close_out is None:
                self.close_out = ""

            # If the user gave no explicit closing tag, infer it from
            # the input tag: <foo> -> </foo>.
            if not self.close_in:
                self.close_in = self.open_in.replace("[zkg", "[/zkg", 1)
            if self.open_out.startswith("[") and not self.close_out:
                self.close_out = self.open_out.replace("[", "[/", 1)

        def apply(self, s: str) -> str:
            """Applies this rule to the given input string and returns the result."""
            return s.replace(self.open_in, self.open_out).replace(
                str(self.close_in or ""),
                str(self.close_out or ""),
            )

    def __init__(self) -> None:
        self.rules: list[Markup.Rule] = []

    def add_rule(self, rule: Rule) -> None:
        self.rules.append(rule)

    def apply(self, s: str) -> str:
        """Applies all rules to the input string, in order, and returns the result."""
        res = s
        for rule in self.rules:
            res = rule.apply(res)
        return res


class PlaintextMarkup(Markup):
    """Basic plaintext markup, mostly discarding it."""

    def __init__(self) -> None:
        super().__init__()
        self.regex = re.compile(r"\[ */? *zkg\..+?\]")

    def apply(self, s: str) -> str:
        res = super().apply(s)
        # Strip out any of our remaining markup tags.
        return re.sub(self.regex, "", res)


class ColorMarkup(Markup):
    """Default color markup of [zkg.*] / [/zkg.*] markup tags."""

    def __init__(self) -> None:
        super().__init__()

        self.add_rule(Markup.Rule("[zkg.pkg]", "[blue1]"))
        self.add_rule(Markup.Rule("[zkg.src]", "[blue1]"))
        self.add_rule(Markup.Rule("[zkg.file]", "[yellow]"))
        self.add_rule(Markup.Rule("[zkg.ver]", "[green]"))
        self.add_rule(Markup.Rule("[zkg.debug]", "[grey66]"))
        self.add_rule(Markup.Rule("[zkg.verbose]", "[grey66]"))
        self.add_rule(Markup.Rule("[zkg.warn]", "[dark_orange]"))
        self.add_rule(Markup.Rule("[zkg.err]", "[red3]"))


class UserInterface(abc.ABC):
    def __init__(self, verbosity: int = 0) -> None:
        self.verbosity = verbosity
        self.markup: Markup = PlaintextMarkup()

    @abc.abstractmethod
    def debug(
        self,
        *msgs: str,
        prefix: str = "Debug:",
        sep: str = " ",
        end: str = "\n",
        flush: bool = False,
    ) -> None:
        """Very verbose messaging, usually to stdout."""
        pass

    @abc.abstractmethod
    def verbose(
        self,
        *msgs: str,
        prefix: str = "Verbose:",
        sep: str = " ",
        end: str = "\n",
        flush: bool = False,
    ) -> None:
        """Verbose messaging, usually to stdout."""
        pass

    @abc.abstractmethod
    def info(
        self,
        *msgs: str,
        prefix: str = "Info:",
        sep: str = " ",
        end: str = "\n",
        flush: bool = False,
    ) -> None:
        """Regular messaging, usually to stdout."""
        pass

    @abc.abstractmethod
    def warning(
        self,
        *msgs: str,
        prefix: str = "Warning:",
        sep: str = " ",
        end: str = "\n",
        flush: bool = False,
    ) -> None:
        """Warnings, usually to stderr."""
        pass

    @abc.abstractmethod
    def error(
        self,
        *msgs: str,
        prefix: str = "Error:",
        sep: str = " ",
        end: str = "\n",
        flush: bool = False,
    ) -> None:
        """Errors, usually to stderr."""
        pass

    @abc.abstractmethod
    def activity(self, act: Activity) -> str:
        """Launch an open-ended activity to completion.

        Once the activity completes, the returned string contains an error
        message if anything went wrong. otherwise the string is empty.
        """
        pass

    @abc.abstractmethod
    def call_activity(self, call: Callable[[], str]) -> str:
        """Launch an open-ended activity to completion.

        The activity is provided in form of the callable.  Once the activity
        completes, the returned string contains an error message if anything
        went wrong. otherwise the string is empty.
        """
        pass

    @abc.abstractmethod
    def progress_activity(self, act: ProgressActivity) -> str:
        """Launch a trackable activity to completion.

        This applies to completions that can track their own progress, knowing
        when they complete.  Once the activity completes, the returned string
        contains an error message if anything went wrong. otherwise the string
        is empty.
        """
        pass

    def confirmation_prompt(self, prompt: str, default_to_yes: bool = True) -> bool:
        """An interactive prompt to obtain confirmation from the user."""
        yes = {"y", "ye", "yes"}

        if default_to_yes:
            prompt += " [Y/n] "
        else:
            prompt += " [N/y] "

        choice = input(prompt).lower()

        if not choice:
            if default_to_yes:
                return True

            print("Abort.")
            return False

        if choice in yes:
            return True

        print("Abort.")
        return False

    def _markup(self, s: str) -> str:
        """Helper to apply markup to a given string."""
        return self.markup.apply(s)

    def _markup_list(self, ss: tuple[str, ...]) -> tuple[str, ...]:
        """Helper to apply markup to a given list of strings."""
        res: list[str] = []
        for s in ss:
            res.append(self.markup.apply(s))
        return tuple(res)


class PlainUI(UserInterface):
    """A basic plaintext UI, suitable for the console or redirection to files."""

    def __init__(
        self,
        verbosity: int = 0,
        stdout: TextIO = sys.stdout,
        stderr: TextIO = sys.stderr,
    ) -> None:
        super().__init__(verbosity=verbosity)
        self.stdout = stdout
        self.stderr = stderr

    def debug(
        self,
        *msgs: str,
        prefix: str = "",
        sep: str = " ",
        end: str = "\n",
        flush: bool = False,
    ) -> None:
        _ = prefix
        if self.verbosity >= 2:
            msgs = self._markup_list(msgs)
            print(*msgs, sep=sep, end=end, file=self.stdout, flush=flush)

    def verbose(
        self,
        *msgs: str,
        prefix: str = "",
        sep: str = " ",
        end: str = "\n",
        flush: bool = False,
    ) -> None:
        _ = prefix
        if self.verbosity >= 1:
            msgs = self._markup_list(msgs)
            print(*msgs, sep=sep, end=end, file=self.stdout, flush=flush)

    def info(
        self,
        *msgs: str,
        prefix: str = "Info:",
        sep: str = " ",
        end: str = "\n",
        flush: bool = False,
    ) -> None:
        msgs = self._markup_list(msgs)
        print(*msgs, sep=sep, end=end, file=self.stdout, flush=flush)

    def warning(
        self,
        *msgs: str,
        prefix: str = "Warning:",
        sep: str = " ",
        end: str = "\n",
        flush: bool = False,
    ) -> None:
        prefix = self._markup(prefix)
        msgs = self._markup_list(msgs)
        if prefix:
            print(prefix, *msgs, sep=sep, end=end, file=self.stderr, flush=flush)
        else:
            print(*msgs, sep=sep, end=end, file=self.stderr, flush=flush)

    def error(
        self,
        *msgs: str,
        prefix: str = "Error:",
        sep: str = " ",
        end: str = "\n",
        flush: bool = False,
    ) -> None:
        prefix = self._markup(prefix)
        msgs = self._markup_list(msgs)
        if prefix:
            print(prefix, *msgs, sep=sep, end=end, file=self.stderr, flush=flush)
        else:
            print(*msgs, sep=sep, end=end, file=self.stderr, flush=flush)

    def activity(self, act: Activity) -> str:
        worker = Worker(act)
        worker.start()
        worker.wait(self.stdout)
        return act.error

    def call_activity(self, call: UiCallable) -> str:
        act = CallableActivity(call)
        worker = Worker(act)
        worker.start()
        worker.wait()
        return act.error

    def progress_activity(self, act: ProgressActivity) -> str:
        worker = Worker(act)
        worker.start()
        worker.wait(self.stdout)
        return act.error


class UIProxy:
    """A proxy for a UI, relaying all calls.

    This allows us to use a toplevel UI object whose implementation we can swap out,
    keeping the global UI working in other modules that imported from this module.
    A toplevel assignment would break the relationship.
    """

    def __init__(self) -> None:
        self.impl: UserInterface = PlainUI()

    def __getattr__(self, name: str) -> Any:
        return getattr(self.impl, name)


try:
    import rich.console  # type: ignore

    class RichUI(UserInterface):
        def __init__(
            self,
            verbosity: int = 0,
            stdout: TextIO = sys.stdout,
            stderr: TextIO = sys.stderr,
        ):
            super().__init__()
            self.verbosity = verbosity
            # Don't use built-in highlighting (of numbers, strings, etc)
            # in our rich consoles. This does not affect our explicit
            # coloring of warnings, packages, etc.
            self.outcon = rich.console.Console(file=stdout, highlight=False)
            self.errcon = rich.console.Console(file=stderr, highlight=False)
            self.markup = ColorMarkup()

        def debug(
            self,
            *msgs: str,
            prefix: str = "",
            sep: str = " ",
            end: str = "\n",
            flush: bool = False,
        ) -> None:
            _ = flush  # ignore flush, rich always flushes
            if self.verbosity >= 2:
                msgs = self._markup_list(msgs)
                self.outcon.print(
                    "[zkg.debug]",
                    *msgs,
                    "[/zkg.debug]",
                    sep=sep,
                    end=end,
                )

        def verbose(
            self,
            *msgs: str,
            prefix: str = "",
            sep: str = " ",
            end: str = "\n",
            flush: bool = False,
        ) -> None:
            _ = flush  # ignore flush, rich always flushes
            if self.verbosity >= 1:
                msgs = self._markup_list(msgs)
                self.outcon.print(
                    "[zkg.verbose]",
                    *msgs,
                    "[/zkg.verbose]",
                    sep=sep,
                    end=end,
                )

        def info(
            self,
            *msgs: str,
            prefix: str = "",
            sep: str = " ",
            end: str = "\n",
            flush: bool = False,
        ) -> None:
            _ = flush  # ignore flush, rich always flushes
            msgs = self._markup_list(msgs)
            self.outcon.print(*msgs, sep=sep, end=end)

        def warning(
            self,
            *msgs: str,
            prefix: str = "[zkg.warn]Warning[/zkg.warn]:",
            sep: str = " ",
            end: str = "\n",
            flush: bool = False,
        ) -> None:
            _ = flush  # ignore flush, rich always flushes
            prefix = self._markup(prefix)
            msgs = self._markup_list(msgs)
            if prefix:
                self.errcon.print(prefix, *msgs, sep=sep, end=end)
            else:
                self.errcon.print(*msgs, sep=sep, end=end)

        def error(
            self,
            *msgs: str,
            prefix: str = "[zkg.err]Error[/zkg.err]:",
            sep: str = " ",
            end: str = "\n",
            flush: bool = False,
        ) -> None:
            _ = flush  # ignore flush, rich always flushes
            prefix = self._markup(prefix)
            msgs = self._markup_list(msgs)
            if prefix:
                self.errcon.print(prefix, *msgs, sep=sep, end=end)
            else:
                self.errcon.print(*msgs, sep=sep, end=end)

        def activity(self, act: Activity) -> str:
            worker = Worker(act)
            worker.start()
            worker.wait()
            return act.error

        def call_activity(self, call: UiCallable) -> str:
            act = CallableActivity(call)
            worker = Worker(act)
            worker.start()
            worker.wait()
            return act.error

        def progress_activity(self, act: ProgressActivity) -> str:
            worker = Worker(act)
            worker.start()
            worker.wait()
            return act.error

except ImportError:
    # Alias the UI back to the plaintext one if we don't have rich.
    RichUI: type[UserInterface] = PlainUI  # type: ignore[no-redef]


def configure(args: argparse.Namespace) -> None:
    """Establish the UI as per the user's preferences and terminal capability."""
    if sys.stdout.isatty():
        UI.impl = RichUI(verbosity=args.verbose)
        return

    UI.impl = PlainUI(verbosity=args.verbose)


UI: UIProxy = UIProxy()
