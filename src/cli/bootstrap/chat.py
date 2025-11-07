from pathlib import Path

from src.cli.bootstrap.timer import enable_timer
from src.cli.core.context import Context
from src.cli.core.session import Session
from src.cli.theme import console


async def handle_chat_command(args) -> int:
    """
    Orchestrates creating a chat context and running a chat session loop according to CLI arguments.
    
    Initializes optional timing, creates a Context from provided CLI arguments, and runs a Session loop that may resume an existing thread, show a welcome message on first non-resume start, and reload the session if requested. Exits with 0 on successful completion or user interrupt, and 1 on unexpected errors (after printing an error).
    
    Parameters:
        args: An object with CLI attributes used to configure the chat:
            - timer: enable periodic timing when truthy
            - agent: agent identifier for the Context
            - model: model identifier for the Context
            - resume: whether to resume an existing thread
            - working_dir: path to use as the working directory
            - approval_mode: approval mode for the Context
    
    Returns:
        int: Exit code — `0` on success or KeyboardInterrupt, `1` on other exceptions.
    """
    try:
        if args.timer:
            enable_timer()

        context = await Context.create(
            agent=args.agent,
            model=args.model,
            resume=args.resume,
            working_dir=Path(args.working_dir),
            approval_mode=args.approval_mode,
        )

        first_start = True
        while True:
            session = Session(context)

            if first_start and args.resume:
                await session.command_dispatcher.resume_handler.handle(
                    context.thread_id
                )

            await session.start(show_welcome=first_start and not args.resume)
            first_start = False

            if session.needs_reload:
                continue
            else:
                break

        return 0
    except KeyboardInterrupt:
        return 0
    except Exception as e:
        console.print_error(f"Error starting chat session: {e}")
        return 1