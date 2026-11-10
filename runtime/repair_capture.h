/* Bounded raw stop capture. Hashing and image admission are separate steps. */
static int plaid_repair_capture(const char *path, const u8 *ram, u32 ram_size,
                                u32 fault, u32 site, u32 target, unsigned long vi) {
  u32 pc = fault == 3 ? target : site;
  u32 p, start, end, i;
  FILE *f;
  if ((fault != 3 && fault != 15) || pc < 0x80000000u || pc >= 0xc0000000u)
    return 0;
  p = pc & 0x1fffffffu;
  if (p >= ram_size || (pc & 3u)) return 0;
  start = p > 0x10000u ? p - 0x10000u : 0;
  end = ram_size - p > 0x10000u ? p + 0x10000u : ram_size;
  f = fopen(path, "wb");
  if (!f) return -1;
  fprintf(f, "{\"format\":\"plaid-repair-raw-v0\",\"fault\":%u,\"site\":\"%08x\","
             "\"target\":\"%08x\",\"vi\":%lu,\"physical_start\":%u,\"bytes\":\"",
          fault, site, pc, vi, start);
  for (i = start; i < end; ++i) fprintf(f, "%02x", ram[i]);
  fputs("\"}\n", f);
  if (ferror(f)) { fclose(f); remove(path); return -1; }
  if (fclose(f)) { remove(path); return -1; }
  return 1;
}
