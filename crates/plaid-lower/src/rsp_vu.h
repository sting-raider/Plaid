
/* ---- vector unit (ADR-0168): ares interpreter-vpu.cpp, scalar (SISD) paths ---- */
static inline u8 plaid_vb(const plaid_v *v, u32 i) {
  i &= 15;
  return (u8)(v->e[i >> 1] >> (i & 1 ? 0 : 8));
}
static inline void plaid_vsb(plaid_v *v, u32 i, u32 b) {
  u32 s;
  i &= 15; s = i & 1 ? 0 : 8;
  v->e[i >> 1] = (u16)((v->e[i >> 1] & ~(0xffu << s)) | (b & 0xff) << s);
}
#define PLAID_DM(a) r->dmem[(a) & 0xfff]
/* the element selector vt(e) */
static inline plaid_v plaid_vsw(plaid_v v, u32 e) {
  plaid_v o;
  u32 n;
  for (n = 0; n < 8; n++) {
    u32 k = e < 2 ? n : e == 2 ? n & ~1u : e == 3 ? n | 1 : e < 8 ? (n & 4) | (e - 4) : e - 8;
    o.e[n] = v.e[k];
  }
  return o;
}
static inline s32 plaid_clamp16(s64 x) { return x > 32767 ? 32767 : x < -32768 ? -32768 : (s32)x; }
static inline u64 plaid_acc_get(plaid_rsp *r, u32 n) {
  return (u64)r->acch.e[n] << 32 | (u64)r->accm.e[n] << 16 | r->accl.e[n];
}
static inline void plaid_acc_set(plaid_rsp *r, u32 n, u64 v) {
  r->acch.e[n] = (u16)(v >> 32); r->accm.e[n] = (u16)(v >> 16); r->accl.e[n] = (u16)v;
}
static inline u16 plaid_acc_sat(plaid_rsp *r, u32 n, int slice, u16 neg, u16 pos) {
  if ((s16)r->acch.e[n] < 0) {
    if (r->acch.e[n] != 0xffff || (s16)r->accm.e[n] >= 0) return neg;
  } else {
    if (r->acch.e[n] != 0 || (s16)r->accm.e[n] < 0) return pos;
  }
  return slice ? r->accm.e[n] : r->accl.e[n];
}
static inline u16 plaid_flag(int b) { return b ? 0xffff : 0; }

/* COP2 moves */
static inline void plaid_mfc2(plaid_rsp *r, u32 rt, u32 vs, u32 e) {
  if (rt) r->r[rt] = (u32)(s32)(s16)(plaid_vb(&r->v[vs], e) << 8 | plaid_vb(&r->v[vs], e + 1));
}
static inline void plaid_mtc2(plaid_rsp *r, u32 rt, u32 vs, u32 e) {
  plaid_vsb(&r->v[vs], e, r->r[rt] >> 8);
  if (e != 15) plaid_vsb(&r->v[vs], e + 1, r->r[rt]);
}
static inline void plaid_cfc2(plaid_rsp *r, u32 rt, u32 rd) {
  static const plaid_v zero;
  const plaid_v *hi = (rd & 3) == 0 ? &r->vcoh : (rd & 3) == 1 ? &r->vcch : &zero;
  const plaid_v *lo = (rd & 3) == 0 ? &r->vcol : (rd & 3) == 1 ? &r->vccl : &r->vce;
  u32 n, v = 0;
  if (!rt) return;
  for (n = 0; n < 8; n++) v |= (u32)(lo->e[n] != 0) << n | (u32)(hi->e[n] != 0) << (8 + n);
  r->r[rt] = (u32)(s32)(s16)v;
}
static inline void plaid_ctc2(plaid_rsp *r, u32 rt, u32 rd) {
  plaid_v null;
  plaid_v *hi = (rd & 3) == 0 ? &r->vcoh : (rd & 3) == 1 ? &r->vcch : &null;
  plaid_v *lo = (rd & 3) == 0 ? &r->vcol : (rd & 3) == 1 ? &r->vccl : &r->vce;
  u32 n, v = r->r[rt];
  for (n = 0; n < 8; n++) { lo->e[n] = plaid_flag(v >> n & 1); hi->e[n] = plaid_flag(v >> (8 + n) & 1); }
}

static const u32 plaid_vmem_scale[12] = {1, 2, 4, 8, 16, 16, 8, 8, 16, 16, 16, 16};
/* LWC2 by its opcode field: address = rs + offset * scale, each byte wrapped at 4 KiB */
static void plaid_lwc2(plaid_rsp *r, u32 op, u32 vt, u32 base, s32 imm, u32 e) {
  u32 a = r->r[base] + (u32)(imm * (s32)plaid_vmem_scale[op]), o, end, index;
  plaid_v *v = &r->v[vt], tmp;
  switch (op) {
  case 0: plaid_vsb(v, e, PLAID_DM(a)); break; /* LBV */
  case 1: case 2: case 3: /* LSV LLV LDV */
    end = e + (2u << (op - 1)); if (end > 16) end = 16;
    for (o = e; o < end; o++) plaid_vsb(v, o, PLAID_DM(a++));
    break;
  case 4: /* LQV */
    end = 16 + e - (a & 15); if (end > 16) end = 16;
    for (o = e; o < end; o++) plaid_vsb(v, o, PLAID_DM(a++));
    break;
  case 5: /* LRV */
    o = 16 - ((a & 15) - e); a &= ~15u;
    for (; o < 16; o++) plaid_vsb(v, o, PLAID_DM(a++));
    break;
  case 6: case 7: /* LPV LUV */
    index = (a & 7) - e; a &= ~7u;
    for (o = 0; o < 8; o++) v->e[o] = (u16)(PLAID_DM(a + ((index + o) & 15)) << (op == 6 ? 8 : 7));
    break;
  case 8: /* LHV */
    index = (a & 7) - e; a &= ~7u;
    for (o = 0; o < 8; o++) v->e[o] = (u16)(PLAID_DM(a + ((index + o * 2) & 15)) << 7);
    break;
  case 9: /* LFV */
    index = (a & 7) - e; a &= ~7u;
    for (o = 0; o < 4; o++) {
      tmp.e[o] = (u16)(PLAID_DM(a + ((index + o * 4) & 15)) << 7);
      tmp.e[o + 4] = (u16)(PLAID_DM(a + ((index + o * 4 + 8) & 15)) << 7);
    }
    end = e + 8; if (end > 16) end = 16;
    for (o = e; o < end; o++) plaid_vsb(v, o, plaid_vb(&tmp, o));
    break;
  case 11: { /* LTV */
    u32 begin = a & ~7u, vtbase = vt & ~7u, vtoff = e >> 1, i;
    a = begin + ((e + (a & 8)) & 15);
    for (i = 0; i < 8; i++) {
      plaid_vsb(&r->v[vtbase + vtoff], i * 2, PLAID_DM(a++));
      if (a == begin + 16) a = begin;
      plaid_vsb(&r->v[vtbase + vtoff], i * 2 + 1, PLAID_DM(a++));
      if (a == begin + 16) a = begin;
      vtoff = (vtoff + 1) & 7;
    }
    break;
  }
  }
}
/* SWC2 by its opcode field */
static void plaid_swc2(plaid_rsp *r, u32 op, u32 vt, u32 base, s32 imm, u32 e) {
  /* SFV: the element stored to each of the four bytes, per e; -1 stores zeros */
  static const s8 sfv[16][4] = {
    {0, 1, 2, 3}, {6, 7, 4, 5}, {-1}, {-1}, {1, 2, 3, 0}, {7, 4, 5, 6}, {-1}, {-1},
    {4, 5, 6, 7}, {-1}, {-1}, {3, 0, 1, 2}, {5, 6, 7, 4}, {-1}, {-1}, {0, 1, 2, 3}};
  u32 a = r->r[base] + (u32)(imm * (s32)plaid_vmem_scale[op]), o, end, index;
  const plaid_v *v = &r->v[vt];
  switch (op) {
  case 0: PLAID_DM(a) = plaid_vb(v, e); break; /* SBV */
  case 1: case 2: case 3: /* SSV SLV SDV */
    for (o = e; o < e + (2u << (op - 1)); o++) PLAID_DM(a++) = plaid_vb(v, o);
    break;
  case 4: /* SQV */
    end = e + (16 - (a & 15));
    for (o = e; o < end; o++) PLAID_DM(a++) = plaid_vb(v, o);
    break;
  case 5: { /* SRV */
    u32 shift = 16 - (a & 15);
    end = e + (a & 15); a &= ~15u;
    for (o = e; o < end; o++) PLAID_DM(a++) = plaid_vb(v, o + shift);
    break;
  }
  case 6: case 7: /* SPV SUV */
    for (o = e; o < e + 8; o++) {
      int packed = ((o & 15) < 8) == (op == 6);
      PLAID_DM(a++) = packed ? plaid_vb(v, (o & 7) << 1) : (u8)(v->e[o & 7] >> 7);
    }
    break;
  case 8: /* SHV */
    index = a & 7; a &= ~7u;
    for (o = 0; o < 8; o++) {
      u32 b = e + o * 2;
      PLAID_DM(a + ((index + o * 2) & 15)) = (u8)(plaid_vb(v, b) << 1 | plaid_vb(v, b + 1) >> 7);
    }
    break;
  case 9: /* SFV */
    index = a & 7; a &= ~7u;
    for (o = 0; o < 4; o++) {
      s8 k = sfv[e][0] < 0 ? -1 : sfv[e][o];
      PLAID_DM(a + ((index + o * 4) & 15)) = k < 0 ? 0 : (u8)(v->e[k] >> 7);
    }
    break;
  case 10: /* SWV */
    index = a & 7; a &= ~7u;
    for (o = e; o < e + 16; o++) PLAID_DM(a + (index++ & 15)) = plaid_vb(v, o);
    break;
  case 11: { /* STV */
    u32 start = vt & ~7u, element = 16 - (e & ~1u);
    index = (a & 7) - (e & ~1u); a &= ~7u;
    for (o = start; o < start + 8; o++) {
      PLAID_DM(a + (index++ & 15)) = plaid_vb(&r->v[o], element++);
      PLAID_DM(a + (index++ & 15)) = plaid_vb(&r->v[o], element++);
    }
    break;
  }
  }
}

/* reciprocal and inverse square root tables, built as ares rsp.cpp builds them */
static const u16 *plaid_rsp_table(int sqrt) {
  static u16 rcp[512], rsq[512];
  static int ready;
  if (!ready) {
    u32 i;
    rcp[0] = 0xffff;
    for (i = 1; i < 512; i++) rcp[i] = (u16)((((u64)1 << 34) / (i + 512) + 1) >> 8);
    for (i = 0; i < 512; i++) {
      u64 a = (i + 512) >> (i % 2 == 1), b = 1 << 17;
      while (a * (b + 1) * (b + 1) < ((u64)1 << 44)) b++;
      rsq[i] = (u16)(b >> 1);
    }
    ready = 1;
  }
  return sqrt ? rsq : rcp;
}
/* VRCP and VRCPL (sqrt 0), VRSQ and VRSQL (sqrt 1) */
static void plaid_vdiv(plaid_rsp *r, int sqrt, int low, u32 vd, u32 de, u32 vt, u32 e) {
  u16 in = r->v[vt].e[e & 7];
  s32 input = low && r->divdp ? (s32)((u32)(u16)r->divin << 16 | in) : (s16)in;
  s32 mask = input >> 31, data = input ^ mask, result;
  if (input > -32768) data -= mask;
  if (data == 0) result = 0x7fffffff;
  else if (input == -32768) result = -65536;
  else {
    u32 shift = (u32)__builtin_clz((u32)data);
    u32 index = (u32)(((u64)(u32)data << shift & 0x7fc00000) >> 22);
    result = sqrt ? plaid_rsp_table(1)[(index & 0x1fe) | (shift & 1)] : plaid_rsp_table(0)[index];
    result = (0x10000 | result) << 14;
    result = (result >> (sqrt ? (31 - shift) >> 1 : 31 - shift)) ^ mask;
  }
  r->divdp = 0;
  r->divout = (s16)(result >> 16);
  r->accl = plaid_vsw(r->v[vt], e);
  r->v[vd].e[de] = (u16)result;
}
/* VRCPH and VRSQH */
static inline void plaid_vdivh(plaid_rsp *r, u32 vd, u32 de, u32 vt, u32 e) {
  r->accl = plaid_vsw(r->v[vt], e);
  r->divdp = 1;
  r->divin = (s16)r->v[vt].e[e & 7];
  r->v[vd].e[de] = (u16)r->divout;
}
static inline void plaid_vmov(plaid_rsp *r, u32 vd, u32 de, u32 vt, u32 e) {
  plaid_v t = plaid_vsw(r->v[vt], e);
  r->v[vd].e[de] = t.e[de];
  r->accl = t;
}

/* Every other computational op, by its function code. vsi is the vs
   register index: VRND reads its low bit. */
static void plaid_vu(plaid_rsp *r, u32 f, u32 vd, u32 vsi, u32 vt, u32 e) {
  plaid_v s = r->v[vsi], t = plaid_vsw(r->v[vt], e), d = r->v[vd];
  u32 n;
  for (n = 0; n < 8; n++) {
    s32 a = (s16)s.e[n], b = (s16)t.e[n];
    u32 ua = s.e[n], ub = t.e[n];
    switch (f) {
    case 0x00: case 0x01: /* VMULF VMULU */
      plaid_acc_set(r, n, (u64)((s64)a * b * 2 + 0x8000));
      if (f == 0) d.e[n] = plaid_acc_sat(r, n, 1, 0x8000, 0x7fff);
      else d.e[n] = (s16)r->acch.e[n] < 0 ? 0 : ((s16)r->acch.e[n] ^ (s16)r->accm.e[n]) < 0 ? 0xffff : r->accm.e[n];
      break;
    case 0x02: case 0x0a: { /* VRNDP VRNDN */
      s32 p = (s32)(vsi & 1 ? (u32)b << 16 : (u32)b);
      s64 acc = (s64)(plaid_acc_get(r, n) << 16) >> 16;
      if (f == 0x0a ? acc < 0 : acc >= 0)
        acc = (s64)(((u64)(acc + p) & 0xffffffffffffull) ^ 0x800000000000ull) - 0x800000000000ll;
      plaid_acc_set(r, n, (u64)acc);
      d.e[n] = (u16)plaid_clamp16(acc >> 16);
      break;
    }
    case 0x03: { /* VMULQ */
      s32 p = a * b;
      if (p < 0) p += 31;
      r->acch.e[n] = (u16)(p >> 16); r->accm.e[n] = (u16)p; r->accl.e[n] = 0;
      d.e[n] = (u16)(plaid_clamp16(p >> 1) & ~15);
      break;
    }
    case 0x04: plaid_acc_set(r, n, (u16)((ua * ub) >> 16)); d.e[n] = r->accl.e[n]; break; /* VMUDL */
    case 0x05: plaid_acc_set(r, n, (u64)(s64)(a * (s32)ub)); d.e[n] = r->accm.e[n]; break; /* VMUDM */
    case 0x06: plaid_acc_set(r, n, (u64)(s64)((s32)ua * b)); d.e[n] = r->accl.e[n]; break; /* VMUDN */
    case 0x07: /* VMUDH */
      plaid_acc_set(r, n, (u64)((s64)(a * b) * 65536));
      d.e[n] = plaid_acc_sat(r, n, 1, 0x8000, 0x7fff);
      break;
    case 0x08: case 0x09: /* VMACF VMACU */
      plaid_acc_set(r, n, plaid_acc_get(r, n) + (u64)((s64)a * b * 2));
      if (f == 8) d.e[n] = plaid_acc_sat(r, n, 1, 0x8000, 0x7fff);
      else d.e[n] = (s16)r->acch.e[n] < 0 ? 0 : (r->acch.e[n] || (s16)r->accm.e[n] < 0) ? 0xffff : r->accm.e[n];
      break;
    case 0x0b: { /* VMACQ */
      s32 p = (s32)((u32)r->acch.e[n] << 16 | r->accm.e[n]);
      if (p < 0 && !(p & 32)) p += 32;
      else if (p >= 32 && !(p & 32)) p -= 32;
      r->acch.e[n] = (u16)(p >> 16); r->accm.e[n] = (u16)p;
      d.e[n] = (u16)(plaid_clamp16(p >> 1) & ~15);
      break;
    }
    case 0x0c: /* VMADL */
      plaid_acc_set(r, n, plaid_acc_get(r, n) + ((ua * ub) >> 16));
      d.e[n] = plaid_acc_sat(r, n, 0, 0, 0xffff);
      break;
    case 0x0d: /* VMADM */
      plaid_acc_set(r, n, plaid_acc_get(r, n) + (u64)(s64)(a * (s32)ub));
      d.e[n] = plaid_acc_sat(r, n, 1, 0x8000, 0x7fff);
      break;
    case 0x0e: /* VMADN */
      plaid_acc_set(r, n, plaid_acc_get(r, n) + (u64)(s64)((s32)ua * b));
      d.e[n] = plaid_acc_sat(r, n, 0, 0, 0xffff);
      break;
    case 0x0f: { /* VMADH */
      s32 res = (s32)(u32)((plaid_acc_get(r, n) >> 16) + (u64)(s64)(a * b));
      r->acch.e[n] = (u16)(res >> 16); r->accm.e[n] = (u16)res;
      d.e[n] = plaid_acc_sat(r, n, 1, 0x8000, 0x7fff);
      break;
    }
    case 0x10: case 0x11: { /* VADD VSUB */
      s32 res = f == 0x10 ? a + b + (r->vcol.e[n] != 0) : a - b - (r->vcol.e[n] != 0);
      r->accl.e[n] = (u16)res; d.e[n] = (u16)plaid_clamp16(res);
      break;
    }
    case 0x13: /* VABS */
      if (a < 0) { r->accl.e[n] = (u16)-b; d.e[n] = b == -32768 ? 32767 : (u16)-b; }
      else if (a > 0) { r->accl.e[n] = (u16)b; d.e[n] = (u16)b; }
      else { r->accl.e[n] = 0; d.e[n] = 0; }
      break;
    case 0x14: { /* VADDC */
      u32 res = ua + ub;
      r->accl.e[n] = (u16)res; r->vcol.e[n] = plaid_flag(res >> 16); d.e[n] = (u16)res;
      break;
    }
    case 0x15: { /* VSUBC */
      u32 res = ua - ub;
      r->accl.e[n] = (u16)res; r->vcol.e[n] = plaid_flag(res >> 16 != 0);
      r->vcoh.e[n] = plaid_flag(res != 0); d.e[n] = (u16)res;
      break;
    }
    case 0x1d: /* VSAR */
      d.e[n] = e == 8 ? r->acch.e[n] : e == 9 ? r->accm.e[n] : e == 10 ? r->accl.e[n] : 0;
      break;
    case 0x20: case 0x21: case 0x22: case 0x23: { /* VLT VEQ VNE VGE */
      int co = r->vcol.e[n] && r->vcoh.e[n], c;
      c = f == 0x20 ? a < b || (a == b && co)
        : f == 0x21 ? !r->vcoh.e[n] && ua == ub
        : f == 0x22 ? ua != ub || r->vcoh.e[n]
        : a > b || (a == b && !co);
      r->vccl.e[n] = plaid_flag(c);
      r->accl.e[n] = (u16)(c ? ua : ub); d.e[n] = r->accl.e[n];
      break;
    }
    case 0x24: /* VCL */
      if (r->vcol.e[n]) {
        if (r->vcoh.e[n]) {
          r->accl.e[n] = (u16)(r->vccl.e[n] ? -ub : ua);
        } else {
          u16 sum = (u16)(ua + ub);
          int carry = (ua + ub) != sum, c = r->vce.e[n] ? (!sum || !carry) : (!sum && !carry);
          r->vccl.e[n] = plaid_flag(c);
          r->accl.e[n] = (u16)(c ? -ub : ua);
        }
      } else if (r->vcoh.e[n]) {
        r->accl.e[n] = (u16)(r->vcch.e[n] ? ub : ua);
      } else {
        int c = (s32)ua - (s32)ub >= 0;
        r->vcch.e[n] = plaid_flag(c);
        r->accl.e[n] = (u16)(c ? ub : ua);
      }
      d.e[n] = r->accl.e[n];
      break;
    case 0x25: /* VCH */
      if ((a ^ b) < 0) {
        s16 res = (s16)(a + b);
        r->accl.e[n] = (u16)(res <= 0 ? -b : a);
        r->vccl.e[n] = plaid_flag(res <= 0); r->vcch.e[n] = plaid_flag(b < 0);
        r->vcol.e[n] = 0xffff;
        r->vcoh.e[n] = plaid_flag(res != 0 && ua != (ub ^ 0xffff));
        r->vce.e[n] = plaid_flag(res == -1);
      } else {
        s16 res = (s16)(a - b);
        r->accl.e[n] = (u16)(res >= 0 ? b : a);
        r->vccl.e[n] = plaid_flag(b < 0); r->vcch.e[n] = plaid_flag(res >= 0);
        r->vcol.e[n] = 0;
        r->vcoh.e[n] = plaid_flag(res != 0 && ua != (ub ^ 0xffff));
        r->vce.e[n] = 0;
      }
      d.e[n] = r->accl.e[n];
      break;
    case 0x26: /* VCR */
      if ((a ^ b) < 0) {
        int c = a + b + 1 <= 0;
        r->vcch.e[n] = plaid_flag(b < 0); r->vccl.e[n] = plaid_flag(c);
        r->accl.e[n] = (u16)(c ? ~ub : ua);
      } else {
        int c = a - b >= 0;
        r->vccl.e[n] = plaid_flag(b < 0); r->vcch.e[n] = plaid_flag(c);
        r->accl.e[n] = (u16)(c ? ub : ua);
      }
      d.e[n] = r->accl.e[n];
      break;
    case 0x27: r->accl.e[n] = (u16)(r->vccl.e[n] ? ua : ub); d.e[n] = r->accl.e[n]; break; /* VMRG */
    case 0x28: r->accl.e[n] = (u16)(ua & ub); d.e[n] = r->accl.e[n]; break;  /* VAND */
    case 0x29: r->accl.e[n] = (u16)~(ua & ub); d.e[n] = r->accl.e[n]; break; /* VNAND */
    case 0x2a: r->accl.e[n] = (u16)(ua | ub); d.e[n] = r->accl.e[n]; break;  /* VOR */
    case 0x2b: r->accl.e[n] = (u16)~(ua | ub); d.e[n] = r->accl.e[n]; break; /* VNOR */
    case 0x2c: r->accl.e[n] = (u16)(ua ^ ub); d.e[n] = r->accl.e[n]; break;  /* VXOR */
    case 0x2d: r->accl.e[n] = (u16)~(ua ^ ub); d.e[n] = r->accl.e[n]; break; /* VNXOR */
    }
  }
  /* flag writes that follow the element loop in ares */
  switch (f) {
  case 0x20: case 0x21: case 0x22: case 0x23:
    memset(&r->vcch, 0, sizeof r->vcch); /* fall through */
  case 0x10: case 0x11: case 0x27:
    memset(&r->vcol, 0, sizeof r->vcol); memset(&r->vcoh, 0, sizeof r->vcoh);
    break;
  case 0x14: memset(&r->vcoh, 0, sizeof r->vcoh); break;
  case 0x24: case 0x26:
    memset(&r->vcol, 0, sizeof r->vcol); memset(&r->vcoh, 0, sizeof r->vcoh); memset(&r->vce, 0, sizeof r->vce);
    break;
  }
  r->v[vd] = d;
}
