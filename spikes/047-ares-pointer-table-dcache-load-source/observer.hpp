#pragma once

// Project-owned research callbacks.  The patched exact-reference build calls
// these only after the corresponding cache/backing operation has completed.
using PlaidDcacheReadObserver = void (*)(u64 pc, u64 vaddr, u32 paddr, u32 size,
  u64 value, u32 tagKey, u16 index, u16 dirty, u64 fillPc, u64 dirtyPc,
  bool hitBefore);
inline PlaidDcacheReadObserver plaidDcacheReadObserver = nullptr;

using PlaidDcacheWriteObserver = void (*)(u64 pc, u64 vaddr, u32 paddr, u32 size,
  u64 value, u32 tagKey, u16 index, u16 dirty, u64 fillPc, u64 dirtyPc,
  bool hitBefore);
inline PlaidDcacheWriteObserver plaidDcacheWriteObserver = nullptr;

using PlaidRdramScalarObserver = void (*)(bool write, u32 address, u32 size,
  u32 device, u64 value);
inline PlaidRdramScalarObserver plaidRdramScalarObserver = nullptr;

using PlaidRdramBurstObserver = void (*)(bool write, u32 address, u32 size,
  u32 device, const u32* words);
inline PlaidRdramBurstObserver plaidRdramBurstObserver = nullptr;
