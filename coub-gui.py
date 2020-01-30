#!/usr/bin/env python3

import os
from textwrap import dedent

from gooey import Gooey, GooeyParser

import coub


class GuiDefaultOptions(coub.DefaultOptions):
    """Custom default option class to reflect the differences between CLI and GUI."""
    # There's no way for the user to enter input if a prompt occurs
    # So only "yes" or "no" make sense
    PROMPT = "no"

    # Outputting to the current dir is a viable strategy for a CLI tool
    # Not so much for a GUI
    if coub.DefaultOptions.PATH == ".":
        PATH = os.path.join(os.path.expanduser("~"), "coubs")
    else:
        PATH = os.path.abspath(coub.DefaultOptions.PATH)

    # "%id%" by itself gets replaced by None anyway and it's less confusing
    # than just showing None as default value
    # This might be worth changing in the main script as well
    if not coub.DefaultOptions.OUT_FORMAT:
        OUT_FORMAT = "%id%"

    # Create special labels for dropdown menus
    # Some internally used values would cause confusion
    # Some menus also combine options
    QUALITY_LABEL = ["Worst quality", "Best quality"]
    AAC_LABEL = ["Only MP3", "No Bias", "Prefer AAC", "Only AAC"]
    RECOUB_LABEL = {
        (True, False): "With Recoubs",
        (False, False): "No Recoubs",
        (True, True): "Only Recoubs",
    }
    SPECIAL_LABEL = {
        (True, False, False): "Share",
        (False, True, False): "Video only",
        (False, False, True): "Audio only",
        (False, False, False): None,
    }


def translate_to_cli(options):
    """Make GUI-specific options object compatible with the main script."""
    # Special dropdown menu labels and what they translate to
    QUALITY_LABEL = {"Worst quality": 0, "Best quality": -1}
    AAC_LABEL = {"Only MP3": 0, "No Bias": 1, "Prefer AAC": 2, "Only AAC": 3}
    RECOUB_LABEL = {
        "With Recoubs": (True, False),
        "No Recoubs": (False, False),
        "Only Recoubs": (True, True),
    }
    SPECIAL_LABEL = {
        "Share": (True, False, False),
        "Video only": (False, True, False),
        "Audio only": (False, False, True),
        None: (False, False, False),
    }

    # Convert GUI labels to valid options for the main script
    options.v_quality = QUALITY_LABEL[options.v_quality]
    options.a_quality = QUALITY_LABEL[options.a_quality]
    options.aac = AAC_LABEL[options.aac]
    options.recoubs, options.only_recoubs = RECOUB_LABEL[options.recoubs]
    options.share, options.v_only, options.a_only = SPECIAL_LABEL[options.special]

    return options


@Gooey(
    program_name="CoubDownloader",
    default_size=(800, 600),
    progress_regex=r"^\[\s*(?P<current>\d+)\/(?P<total>\d+)\](.*)$",
    progress_expr="current / total * 100",
    tabbed_groups=True,
    show_success_modal=False,
    show_failure_modal=False,
    hide_progress_msg=False,
    terminal_font_family="monospace", # didn't work when I tested it on Windows
)
def parse_cli():
    """Create Gooey GUI."""
    defs = GuiDefaultOptions()
    parser = GooeyParser(
        description="Download videos from coub.com",
        usage="%(prog)s [OPTIONS] INPUT [INPUT]..."
    )

    # Input
    input_ = parser.add_argument_group(
        "Input",
        description="Specify various input sources\n\n"
                    "All input fields support several items (i.e. names, IDs, "
                    "tags, etc.). Items must be comma-separated.",
        gooey_options={'columns': 1}
    )
    input_.add_argument("--urls", default="", metavar="Direct URLs",
                        help="Provide direct URL input")
    input_.add_argument("--ids", default="", metavar="Coub IDs",
                        help="Download coubs with the given IDs")
    input_.add_argument("--channels", default="", metavar="Channels",
                        help="Download channels with the given names")
    input_.add_argument("--recoubs", metavar="Recoubs",
                        default=defs.RECOUB_LABEL[(defs.RECOUBS, defs.ONLY_RECOUBS)],
                        choices=["With Recoubs", "No Recoubs", "Only Recoubs"],
                        help="How to treat recoubs during channel downloads")
    input_.add_argument("--tags", default="", metavar="Tags",
                        help="Download coubs with at least one of the given tags")
    input_.add_argument("--searches", default="", metavar="Search Terms",
                        help="Download search results for the given terms")
    input_.add_argument("--communities", default="", metavar="Communities",
                        help="Download coubs from the given communities")
    input_.add_argument("--lists", default="", widget="MultiFileChooser",
                        metavar="Link Lists", help="Read coub links from input lists",
                        gooey_options={'message': "Choose link lists"})
    input_.add_argument("--random", action="count", metavar="Random",
                        help="Download N*1000 randomly generated coubs")
    input_.add_argument("--hot", action="store_true", widget="BlockCheckbox",
                        metavar="Hot Section", help="Download coubs from the hot section")

    # Common Options
    common = parser.add_argument_group("General", gooey_options={'columns': 1})
    common.add_argument("--prompt", choices=["yes", "no"], default=defs.PROMPT,
                        metavar="Prompt Behavior", help="How to answer user prompts")
    common.add_argument("--repeat", type=coub.positive_int, default=defs.REPEAT,
                        metavar="Loop Count", help="How often to loop the video stream")
    common.add_argument("--dur", type=coub.valid_time, default=defs.DUR,
                        metavar="Limit duration",
                        help="Max. duration of the output (FFmpeg syntax)")
    common.add_argument("--preview", default=defs.PREVIEW, metavar="Preview Command",
                        help="Command to invoke to preview each finished coub")
    common.add_argument("--archive-path", type=coub.valid_archive,
                        default=defs.ARCHIVE_PATH, widget="FileSaver",
                        metavar="Archive", gooey_options={'message': "Choose archive file"},
                        help="Use an archive file to keep track of already downloaded coubs")
    common.add_argument("--keep", action=f"store_{'false' if defs.KEEP else 'true'}",
                        widget="BlockCheckbox", metavar="Keep streams",
                        help="Whether to keep the individual streams after merging")

    # Download Options
    download = parser.add_argument_group("Download", gooey_options={'columns': 1})
    download.add_argument("--connect", type=coub.positive_int,
                          default=defs.CONNECT, metavar="Number of connections",
                          help="How many connections to use (>100 not recommended)")
    download.add_argument("--retries", type=int, default=defs.RETRIES,
                          metavar="Retry Attempts",
                          help="How often to reconnect to Coub after connection loss "
                               "(<0 for infinite retries)")
    download.add_argument("--max-coubs", type=coub.positive_int,
                          default=defs.MAX_COUBS, metavar="Limit Quantity",
                          help="How many coub links to parse")

    # Format Selection
    formats = parser.add_argument_group("Format", gooey_options={'columns': 1})
    formats.add_argument("--v-quality", choices=["Best quality", "Worst quality"],
                         default=defs.QUALITY_LABEL[defs.V_QUALITY],
                         metavar="Video Quality", help="Which video quality to download")
    formats.add_argument("--a-quality", choices=["Best quality", "Worst quality"],
                         default=defs.QUALITY_LABEL[defs.A_QUALITY],
                         metavar="Audio Quality", help="Which audio quality to download")
    formats.add_argument("--v-max", choices=["med", "high", "higher"],
                         default=defs.V_MAX, metavar="Max. Video Quality",
                         help="Cap the max. video quality considered for download")
    formats.add_argument("--v-min", choices=["med", "high", "higher"],
                         default=defs.V_MIN, metavar="Min. Video Quality",
                         help="Cap the min. video quality considered for download")
    formats.add_argument("--aac", default=defs.AAC_LABEL[defs.AAC],
                         choices=["Only MP3", "No Bias", "Prefer AAC", "Only AAC"],
                         metavar="Audio Format", help="How much to prefer AAC over MP3")
    formats.add_argument("--special", choices=["Share", "Video only", "Audio only"],
                         default=defs.SPECIAL_LABEL[(defs.SHARE, defs.V_ONLY, defs.A_ONLY)],
                         metavar="Special Formats", help="Use a special format selection")

    # Output
    output = parser.add_argument_group("Output", gooey_options={'columns': 1})
    output.add_argument("--out-file", type=os.path.abspath, widget="FileSaver",
                        default=defs.OUT_FILE, metavar="Output to List",
                        gooey_options={'message': "Save link list"},
                        help="Save all parsed links in a list (no download)")
    output.add_argument("--path", type=os.path.abspath, default=defs.PATH,
                        widget="DirChooser", metavar="Output Directory",
                        help="Where to save downloaded coubs",
                        gooey_options={
                            'message': "Pick output destination",
                            'default_path': defs.PATH,
                        })
    output.add_argument("--merge-ext", default=defs.MERGE_EXT,
                        metavar="Output Container",
                        choices=["mkv", "mp4", "asf", "avi", "flv", "f4v", "mov"],
                        help="What extension to use for merged output files "
                             "(has no effect if no merge is required)")
    output.add_argument("--out-format", default=defs.OUT_FORMAT,
                        metavar="Name Template",
                        help=dedent(f"""\
                            Change the naming convention of output files

                            Special strings:
                              %id%        - coub ID (identifier in the URL)
                              %title%     - coub title
                              %creation%  - creation date/time
                              %community% - coub community
                              %channel%   - channel title
                              %tags%      - all tags (separated by _)

                            Other strings will be interpreted literally
                            This option has no influence on the file extension
                            """))

    # Advanced Options
    parser.set_defaults(
        verbosity=1,
        coubs_per_page=25,      # allowed: 1-25
        tag_sep="_",
        write_method="w",       # w -> overwrite, a -> append
    )

    args = parser.parse_args()
    args.input = []
    args.input.extend([coub.mapped_input(u) for u in args.urls.split(",") if u])
    args.input.extend([f"https://coub.com/view/{i}" for i in args.ids.split(",") if i])
    args.input.extend([coub.LinkList(l) for l in args.lists.split(",") if l])
    args.input.extend([coub.Channel(c) for c in args.channels.split(",") if c])
    args.input.extend([coub.Tag(t) for t in args.tags.split(",") if t])
    args.input.extend([coub.Search(s) for s in args.searches.split(",") if s])
    args.input.extend([coub.Community(c) for c in args.communities.split(",") if c])
    if args.hot:
        args.input.append(coub.HotSection())
    if args.random:
        for _ in range(args.random):
            args.input.append(coub.RandomCategory())

    # Read archive content
    if args.archive_path and os.path.exists(args.archive_path):
        with open(args.archive_path, "r") as f:
            args.archive = [l.strip() for l in f]
    else:
        args.archive = None
    # The default naming scheme is the same as using %id%
    # but internally the default value is None
    if args.out_format == "%id%":
        args.out_format = None

    return translate_to_cli(args)


if __name__ == '__main__':
    coub.opts = parse_cli()
    coub.main()
