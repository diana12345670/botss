# NZ Apostado - Discord Betting Bot

## Overview

NZ Apostado is a Discord bot that manages a betting system with queue management, automated private channel creation, and bet mediation. The bot allows users to join betting queues for different game modes (1v1 Mixed, 1v1 Mob, 2v2 Mixed), automatically matches players, creates private channels for matched bets, handles payment confirmations, and manages bet finalization through mediators.

The system is built using Python with the discord.py library and implements a file-based JSON storage solution for managing queues, active bets, and bet history.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Application Structure

**Problem:** Need to organize a Discord bot with betting logic, data persistence, and command handling.

**Solution:** Modular architecture separating concerns:
- `main.py` - Bot initialization, Discord event handlers, and slash commands
- `models/bet.py` - Data model for bet representation
- `utils/database.py` - Data persistence layer with JSON file storage
- `data/bets.json` - Persistent storage for queues, active bets, and history

**Rationale:** This separation allows independent development and testing of business logic, data models, and Discord integration. The dataclass-based Bet model provides type safety and clear data structure.

### Bot Framework

**Problem:** Need to interact with Discord API and handle user commands.

**Solution:** Discord.py library with slash commands (app_commands) for modern Discord UX.

**Key decisions:**
- Uses `discord.ext.commands.Bot` as the base bot class
- Implements Discord Intents for message content, member data, and guild access
- Uses slash commands (`@bot.tree.command`) instead of traditional prefix commands for better discoverability

**Alternatives considered:** Traditional prefix commands (e.g., `!command`) were available but slash commands provide better user experience and autocomplete functionality.

### Data Persistence

**Problem:** Need to persist betting queues, active bets, and historical data across bot restarts.

**Solution:** JSON file-based storage with a database abstraction layer (`Database` class).

**Structure:**
```json
{
  "queues": {},           // Mode-specific player queues
  "active_bets": {},      // Currently ongoing bets
  "bet_history": []       // Completed bet records
}
```

**Pros:**
- Simple setup with no external database dependencies
- Human-readable format for debugging
- Easy to version control and backup

**Cons:**
- Not suitable for high-concurrency scenarios
- Limited query capabilities
- Potential data loss if file corruption occurs

**Alternatives considered:** SQL databases (SQLite, PostgreSQL) would provide better concurrency and query capabilities but add complexity for this use case.

### Bet Lifecycle Management

**Problem:** Manage complex state transitions for bets from queue → matching → confirmation → completion.

**Solution:** State machine pattern using the `Bet` dataclass with boolean flags for confirmation states.

**States tracked:**
- Queue membership (managed by Database)
- Active bet creation (player pairing)
- Payment confirmations (`player1_confirmed`, `player2_confirmed`)
- Winner declaration (`winner_id`)
- Timestamps (`created_at`, `finished_at`)

**Anti-duplication mechanism:** `is_user_in_active_bet()` method prevents users from joining multiple bets simultaneously.

### Channel Management

**Problem:** Create private, temporary channels for matched betting pairs.

**Solution:** Automatic channel creation under "💰・Apostas Ativas" category with permission-based access control.

**Access control:**
- Only matched players can view/interact
- Mediator has full access
- Bot has management permissions
- Channel auto-deletion after bet completion (30-second delay)

### Command Interface

**Problem:** Provide user-friendly betting commands.

**Solution:** Discord slash commands with choices for game modes.

**Implemented commands:**
- `/entrar-fila` - Join betting queue with mode selection
- `/sair-fila` - Leave betting queue
- `/ver-filas` - View queue status
- `/confirmar-pagamento` - Confirm payment sent to mediator
- `/finalizar-aposta` - [Mediator only] Finalize bet and declare winner
- `/cancelar-aposta` - [Mediator only] Cancel ongoing bet
- `/historico` - View bet history
- `/minhas-apostas` - View your active bets
- `/ajuda` - View all available commands

**Choice pattern:** Uses `app_commands.Choice` to provide predefined options, preventing invalid mode inputs.

### Race Condition Prevention

**Problem:** Concurrent queue matches could create duplicate active bets for the same player.

**Solution:** Provisional bet reservation system.

**Implementation:**
1. Before any async Discord API calls, create a provisional active bet (blocks concurrent matches)
2. Remove players from ALL queues (not just current mode)
3. On success: replace provisional bet with real bet
4. On failure: remove provisional bet and re-queue players

This ensures atomic player reservation and prevents race conditions in high-traffic scenarios.

### Mediator Selection

**Problem:** Ensure mediator is always independent from matched players.

**Solution:** Strict filtering and validation.

**Implementation:**
- Filter guild members to exclude bots AND both players
- If no valid mediators available: abort creation and re-queue players
- Never allows a player to be their own mediator, even in small guilds

## Recent Changes

### November 19, 2025 - Persistent Queue Panels
**Problem:** Queue panels were becoming invalid after a few hours, requiring mediators to constantly create new panels.

**Solution:** Implemented permanent metadata persistence:
- Queue metadata is now **never deleted**, even when messages are deleted
- Panels can be reused indefinitely - same panel works for multiple matches
- Fixed issue where metadata was being cleared on message deletion
- Improved error messages to guide users when encountering legacy panels
- System automatically preserves panel configuration across bot restarts

**Impact:** 
- ✅ Panels work forever - no more "invalid" messages
- ✅ Same panel can handle unlimited matches
- ✅ Works perfectly on Fly.io with automatic persistence
- ✅ Both `/mostrar-fila` and `/preset-filas` panels remain functional indefinitely

**Technical Details:**
- Modified `on_message_delete` event to preserve metadata while clearing player lists
- Queue metadata stays in database permanently
- Player lists are cleared but panel configuration persists

### October 23, 2025 - Complete Bot Implementation
- Implemented full betting system with queue management
- Added private channel creation with access control
- Payment confirmation system with mediator notifications
- Bet finalization with automatic channel cleanup
- Comprehensive logging and history tracking

### Critical Bug Fixes
- Fixed race condition allowing duplicate active bets
- Fixed mediator selection to prevent players being their own mediator
- Added provisional bet system for atomic player reservation
- Added queue restoration on failed bet creation

### Configuration Management

**Problem:** Store sensitive data like bot tokens and PIX keys.

**Solution:** Environment variables for secrets, constants for static configuration.

- Bot token: Environment variable `TOKEN` (referenced in README)
- PIX key: Hardcoded constant `MEDIATOR_PIX` (should be environment variable)
- Game modes: Python list constant `MODES`

## External Dependencies

### Discord.py Library

**Purpose:** Primary framework for Discord bot functionality.

**Features used:**
- `discord.ext.commands` - Bot command framework
- `discord.app_commands` - Slash command implementation
- `discord.Intents` - Gateway intents for accessing Discord events
- Discord object models (User, Channel, Guild, etc.)

**Required intents:**
- Message Content Intent (privileged)
- Server Members Intent (privileged)
- Presence Intent (privileged)

### Python Standard Library

**Dependencies:**
- `json` - Data serialization/deserialization
- `os` - File system operations and environment variables
- `datetime` - Timestamp generation
- `random` - Likely used for mediator selection or bet ID generation
- `dataclasses` - Type-safe data models
- `typing` - Type hints for better code documentation

### Discord Developer Portal

**Purpose:** Bot registration and permission management.

**Configuration required:**
- Application/bot creation
- Privileged gateway intents enablement
- OAuth2 URL generation for bot invitation
- Bot token generation

### File System

**Purpose:** Persistent storage backend.

**Requirements:**
- Read/write access to `data/` directory
- JSON file persistence (`data/bets.json`)

**Note:** The current implementation uses JSON file storage, but the architecture would support migration to a relational database (e.g., PostgreSQL) if needed for scalability.