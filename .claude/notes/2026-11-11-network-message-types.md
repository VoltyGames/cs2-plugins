# Network message types after CS2 build 2000943 (2026-11-11)

Status: worked around in voltmod. Remove the workaround once s2sdk declares the new networksystem
layout; upstream had not, as of s2sdk `21654ee5` (2026-11-11).

## What the update changed (networksystem, build 2000943)

- `INetworkMessages` lost `Serialize`, `SerializeAbstract`, `AllocateAndCopyConstructNetMessageAbstract`
  and `DeallocateNetMessageAbstract`, and gained one virtual at slot 20: the `"%s [%d]"` registration
  that `CNetMessage::GetNetMessage` now calls lazily. 36 slots on Windows, 37 on Linux (two
  destructors, at the end). `FindNetworkMessage` is slot 9 and `FindNetworkMessagePartial` slot 10 on
  both; the SDK still says 13 and 14. Everything after slot 20 is 3 below the SDK.
- `INetworkMessageInternal` is no longer an interface. It is a 0x28-byte record without a vtable:
  `+0x00` `CUtlString` name (`"CUserMessageTextMsg [124]"`), `+0x08` `CNetMessage* (*)()` factory,
  `+0x10` `CUtlString` group, `+0x18` `int` message id, `+0x1c`/`+0x20` category ints, `+0x24` group
  id, `+0x25` buf-type and flag bits. `INetworkMessages::GetNetMessageInfo(p)` returns `p`. No
  `IProtobufBinding` hangs off a type any more.
- `CNetMessage` lost `GetName`, its last virtual. The layout is unchanged (proto at `+0x30`), and its
  deleting destructor frees through `g_pMemAlloc`.
- `IGameEventSystem` is unchanged (21 slots on both platforms).

Symptom: the host crashed on load in `ButtonPresses::Install`. The SDK's `FindNetworkMessagePartial`
slot now holds `GetNetworkGroupColor`, and the message `GetNetMessageInfo()` read went through
`0xffffffffffffffff`. Every message send, `ConVars::SendToClient` and the `TextMessages` hook were
broken the same way.

## Proof

Read from the 2000943 `networksystem.dll` and `libnetworksystem.so`. The build archive keeps only
server and engine2, so `libnetworksystem.so` came from DepotDownloader. Slots 9 and 10 were told
apart by their imports: `V_stricmp_fast` versus `V_stristr_fast`. The other slots were placed by
strings and the fields they touch. The record layout came from the slot-20 registration, from
`FindNetworkMessage` comparing `[type+0]` with the name, from `FindNetworkMessageById` comparing
`[type+0x18]` on both platforms, and from the `CNETMsg_NOP` factory.

The local Windows server then loaded host 1.8.7 (`0e1aafa` plus this change) and all five plugins on
2000943. It installed the button-press hook, logged `Client convar queries enabled` in each plugin,
and wrote no crash dump. Linux has been checked only from the binary, and nothing has yet sent a
message to a connected client.

## What is in place

- `voltmod/src/Engine/Net/MessageTypes.{hpp,cpp}`:
  - `FindMessageType` calls vtable slot 10 directly.
  - `ReadMessageId` reads `+0x18`.
  - `AllocateMessage` calls the `+0x08` factory.
  - `FreeMessage` deletes through the virtual destructor.
- The callers go through it: `PostUserMessage` (TextMsg, Shake, votes), `ConVars::SendToClient`,
  `ClientConVars`, the `TextMessages` hook, `ButtonPresses` and `WorkshopDownloads`.
- The public headers still hold an opaque `INetworkMessageInternal*`, so consumers do not change.

## Proper fix

1. After `git -C references/s2sdk fetch`, watch
   `git -C references/s2sdk log origin/cs2 -- public/networksystem/`.
2. When `inetworkmessages.h` and `inetworkserializer.h` model the record and the shorter
   `INetworkMessages`, replace the four helpers with SDK calls, delete `MessageTypes.*`, and grep for
   `MessageTypes.hpp`.
3. Until then, call nothing else through the SDK's `INetworkMessages` or `INetworkMessageInternal`
   declarations. Every slot past 2 is wrong, and the record has no virtuals.

## Follow-ups

- `voltmod framework gamedata fetch` archives only server and engine2. Archiving networksystem too
  would have made this diffable against the old build.
- The CS2 update also moved the Linux `CNetworkGameServer::ReplyConnection` prologue; its gamedata
  pattern was updated the same day.
