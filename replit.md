# StormBet Apostas - Discord Betting Bot

## Overview

StormBet Apostas is a Discord bot that manages a betting system with queue management, automated private channel creation, and bet mediation. The bot allows users to join betting queues for different game modes (1v1 Mixed, 1v1 Mob, 2v2 Mixed), automatically matches players, creates private channels for matched bets, handles payment confirmations, and manages bet finalization through mediators.

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

**Problem:** Need to persist betting queues, active bets, and historical data across bot restarts, especially on platforms that "sleep" and lose file data.

**Solution:** Hybrid database system with PostgreSQL (optional) + JSON (fallback and backup).

**Architecture:**
- **Primary (with DATABASE_URL):** PostgreSQL with JSONB column
- **Backup:** Always maintains JSON files as safety layer
- **Fallback:** If PostgreSQL fails, automatically uses JSON
- **Triple Backup System:** 3 rotating JSON files (bets.json, bets.backup.json, bets.backup2.json)

**Structure:**
```json
{
  "queues": {},             // Mode-specific player queues
  "queue_timestamps": {},   // Queue creation timestamps
  "queue_metadata": {},     // Panel metadata (permanent)
  "active_bets": {},        // Currently ongoing bets
  "bet_history": [],        // Completed bet records
  "mediator_roles": {},     // Guild mediator configurations
  "results_channels": {},   // Results announcement channels
  "subscriptions": {}       // User notification preferences
}
```

**Pros:**
- ✅ PostgreSQL provides persistence on platforms like Render, Railway, Fly.io
- ✅ JSON backup ensures data never lost even if PostgreSQL fails
- ✅ Triple backup system protects against file corruption
- ✅ Automatic fallback - no manual intervention needed
- ✅ Works with or without PostgreSQL - fully flexible

**Cons:**
- Requires PostgreSQL for production deployments on platforms that clear files
- Slightly more complex than pure JSON

**Implementation Details:**
- Uses `psycopg2.extras.RealDictCursor` for automatic JSONB→dict conversion
- Uses `psycopg2.extras.Json()` for proper dict→JSONB serialization
- Connection pooling (1-10 connections) for better performance
- Automatic schema creation on first run
- Validates data integrity on every read/write

**Platforms:**
- **Replit:** Works with built-in PostgreSQL (DATABASE_URL auto-configured)
- **Render:** Requires PostgreSQL addon ($7/month) for persistence
- **Railway/Fly.io:** Supports both modes, PostgreSQL recommended

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

### November 20, 2025 - Hybrid Database System
**Problem:** Data loss on platforms like Render free tier that clear files when service "sleeps".

**Solution:** Implemented hybrid PostgreSQL + JSON system:
- **PostgreSQL Integration:** Optional PostgreSQL support with automatic JSONB handling
- **Triple Backup System:** 3 rotating JSON backups for data safety
- **Automatic Fallback:** Seamlessly switches to JSON if PostgreSQL unavailable
- **Zero Data Loss:** Multiple layers of redundancy ensure queue data never lost
- **Platform Flexibility:** Works perfectly on Replit, Render, Railway, Fly.io

**Technical Implementation:**
- Fixed critical JSONB serialization bug using `RealDictCursor` and `psycopg2.extras.Json`
- Added data validation on every read/write operation
- Connection pooling for optimal PostgreSQL performance
- Automatic schema creation and migration
- Comprehensive logging for monitoring

**Impact:**
- ✅ Production-ready on all platforms
- ✅ Queue data persists through service restarts and sleep cycles
- ✅ Backward compatible - existing JSON data automatically migrates
- ✅ No user intervention needed - automatic detection and configuration

**Documentation:** See [SISTEMA_HIBRIDO.md](SISTEMA_HIBRIDO.md) for complete details.

### November 20, 2025 - Branding Update
- Updated all documentation from "NZ Apostas" to "StormBet Apostas"
- Updated emails, domains, and app names across 12+ files
- Maintained all functionality while refreshing brand identity

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