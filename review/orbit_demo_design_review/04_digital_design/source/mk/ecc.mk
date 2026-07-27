# ECC extension (area: ecc): (72,64) Hsiao SECDED codec and a small
# bit-interleaved, scrubbed storage bank. Target-architecture item "Protected
# SRAM / SECDED ECC + interleaving / ECC scrub"; NOT part of orbit_demo.
# Owner: ecc area (rtl/ecc/, tb/ecc/, formal/ecc/, mk/ecc.mk, reports/ecc/).
#
#   make ecc              everything below except ecc-report: lint, H-matrix check,
#                         simulation, formal (proofs, covers, negative controls),
#                         simulation negative controls and synthesis; non-zero exit
#                         on any failure (about 14 minutes; results in reports/ecc/results.txt)
#   make ecc-quick        fast subset for `make test` (TEST_TARGETS): lint, H-matrix
#                         check, codec simulation, a short bank simulation, the codec
#                         proof and the fault-free bank proof
#   make ecc-lint         Verilator -Wall lint and Icarus -Wall compile of $(ECC_RTL)
#   make ecc-hsiao        the H matrix in the codec equals the Hsiao construction of
#                         $(ECC_RTL_DIR)/gen_hsiao72.py and has its properties
#   make ecc-sim          tb/ecc/tb_orbit_secded72.v (exhaustive single/double errors
#                         over random words) and tb/ecc/tb_orbit_ecc_bank.v (random
#                         traffic and upsets vs a reference model) for ECC_SIM_SEEDS
#   make ecc-sim-mutants  both benches on each broken copy from tb/ecc/ecc_mutants.py:
#                         at least one bench must FAIL on every mutant
#   make ecc-formal       formal/ecc/*.sby: codec proof, bank proofs (clean, sec, ded),
#                         covers, bounded end-to-end BMC with the real decoder, and
#                         negative controls that must FAIL (il1_neg, codec_even_col,
#                         bank_no_writeback and bank_read_way_swap: BMC from reset,
#                         task sec_bmc)
#   make ecc-synth        Yosys generic synthesis of the encoder, decoder and bank:
#                         check -assert, no latches, codec without flip-flops, bank
#                         flip-flop count as designed; statistics in $(ECC_OUT)/synth/
#   make ecc-report       ecc, then copy the result summaries and trimmed logs to
#                         $(ECC_REPORT_DIR)/ (only when RTL_DIR is the production rtl)
#
# Everything reads $(ECC_RTL) (from $(RTL_DIR)/ecc/) and writes under
# $(BUILD)/ecc/, so `make RTL_DIR=<copy> BUILD=<dir> ecc` checks a modified copy.
# Each check writes one result line to $(ECC_OUT)/results/<check>.txt
# ("OK ..." or "BAD ..."); `ecc` prints them all at the end.

ECC_RTL_DIR        := $(RTL_DIR)/ecc
ECC_CODEC          := $(ECC_RTL_DIR)/orbit_secded72.v
ECC_BANK           := $(ECC_RTL_DIR)/orbit_ecc_bank.v
ECC_RTL            := $(ECC_CODEC) $(ECC_BANK)
ECC_GEN            := $(ECC_RTL_DIR)/gen_hsiao72.py
ECC_OUT            := $(BUILD)/ecc
ECC_RES            := $(ECC_OUT)/results
ECC_TB_DIR         := tb/ecc
ECC_FV_DIR         := formal/ecc
ECC_PY             ?= python3
ECC_IVERILOG       ?= iverilog -g2005 -Wall -Wno-timescale
ECC_SIM_SEEDS      ?= 1 2
ECC_SIM_CYCLES     ?= 15000
ECC_QUICK_CYCLES   ?= 3000
ECC_MUT_CYCLES     ?= 3000
ECC_FORMAL_TIMEOUT ?= 1200
ECC_REPORT_DIR     ?= reports/ecc
ECC_MUTANTS        := codec_even_col bank_no_writeback bank_no_interleave bank_cnt_wrap \
                      bank_log_prio bank_scrub_on_read bank_read_way_swap

# Bank proof tasks (formal/ecc/orbit_ecc_bank.sby) and their expected status.
ECC_FV_PASS_TASKS  := clean sec ded cover cover_ded e2e_clean e2e_upset
ECC_FV_FAIL_TASKS  := il1_neg

ECC_RUN_SBY         = bash $(ECC_FV_DIR)/run_sby.sh
# $(call ECC_SBY_GEN,<template>,<out.sby>,<codec>,<bank>): fill in the source paths.
ECC_SBY_GEN         = mkdir -p $(dir $(2)) && sed \
                      -e 's|@CODEC@|$(abspath $(3))|' -e 's|@BANK@|$(abspath $(4))|' \
                      -e 's|@DECABS@|$(abspath $(ECC_FV_DIR)/orbit_secded72_dec_abs.v)|' \
                      -e 's|@HARNESS@|$(abspath $(ECC_FV_DIR)/orbit_ecc_bank_fv.sv)|' \
                      -e 's|@E2E@|$(abspath $(ECC_FV_DIR)/orbit_ecc_bank_e2e_fv.sv)|' \
                      -e 's|@CODEC_HARNESS@|$(abspath $(ECC_FV_DIR)/orbit_secded72_fv.sv)|' \
                      $(1) > $(2)
# $(call ECC_RESULT,<name>,<command>,<ok text>): run a command, record OK/BAD.
ECC_RESULT          = mkdir -p $(ECC_RES); \
                      if $(2); then echo "OK  $(1) $(3)" | tee $(ECC_RES)/$(1).txt; \
                      else echo "BAD $(1)" | tee $(ECC_RES)/$(1).txt; exit 1; fi

.PHONY: ecc ecc-quick ecc-lint ecc-hsiao ecc-sim ecc-sim-codec ecc-sim-bank ecc-sim-quick \
        ecc-sim-mutants ecc-formal ecc-formal-codec ecc-formal-bank ecc-formal-clean \
        ecc-formal-neg ecc-synth ecc-report ecc-summary

TEST_TARGETS += ecc-quick

# `ecc` keeps going after a failed check so that the summary lists all of
# them, then fails if any check did.
ecc:
	@rm -rf $(ECC_RES)
	@fail=0; \
	for t in ecc-lint ecc-hsiao ecc-sim ecc-sim-mutants ecc-formal ecc-synth; do \
	    $(MAKE) --no-print-directory $$t || fail=1; \
	done; \
	$(MAKE) --no-print-directory ecc-summary; \
	if [ $$fail -ne 0 ]; then echo "ECC: FAIL"; exit 1; fi; echo "ECC: PASS"

ecc-quick: ecc-lint ecc-hsiao ecc-sim-codec ecc-sim-quick ecc-formal-codec ecc-formal-clean
	@echo "ECC-QUICK: PASS"

ecc-summary:
	@mkdir -p $(ECC_RES)
	@cat $(ECC_RES)/*.txt | tee $(ECC_OUT)/summary.txt
	@! grep -q '^BAD' $(ECC_OUT)/summary.txt

# ----------------------------------------------------------------------------
# Lint and H-matrix check
# ----------------------------------------------------------------------------
ecc-lint:
	@mkdir -p $(ECC_OUT)/lint
	@$(call ECC_RESULT,lint,verilator --lint-only -Wall --top-module orbit_ecc_bank $(ECC_RTL) \
	    > $(ECC_OUT)/lint/verilator.log 2>&1 && \
	  $(ECC_IVERILOG) -o $(ECC_OUT)/lint/bank.vvp -s orbit_ecc_bank $(ECC_RTL) \
	    > $(ECC_OUT)/lint/iverilog.log 2>&1 && \
	  ! grep -q -i warning $(ECC_OUT)/lint/iverilog.log,Verilator -Wall and Icarus -Wall clean)

ecc-hsiao:
	@mkdir -p $(ECC_OUT)
	@$(call ECC_RESULT,hsiao,$(ECC_PY) $(ECC_GEN) --check $(ECC_CODEC) > $(ECC_OUT)/hsiao.log 2>&1,\
	  H matrix = Hsiao construction (72 distinct odd-weight columns; 26 ones per data row))
	@cat $(ECC_OUT)/hsiao.log

# ----------------------------------------------------------------------------
# Simulation
# ----------------------------------------------------------------------------
ecc-sim: ecc-sim-codec ecc-sim-bank

ecc-sim-codec:
	@mkdir -p $(ECC_OUT)/sim
	@$(ECC_IVERILOG) -o $(ECC_OUT)/sim/tb_codec.vvp $(ECC_TB_DIR)/tb_orbit_secded72.v $(ECC_CODEC)
	@$(call ECC_RESULT,sim_codec,vvp -n $(ECC_OUT)/sim/tb_codec.vvp +seed=1 \
	    > $(ECC_OUT)/sim/codec_seed1.log 2>&1 && \
	  grep -q '^TB_ORBIT_SECDED72 PASS' $(ECC_OUT)/sim/codec_seed1.log,\
	  every single and double error position over random words (log sim/codec_seed1.log))
	@sed -n '/summary/,/PASS\|FAIL/p' $(ECC_OUT)/sim/codec_seed1.log

$(ECC_OUT)/sim/tb_bank.vvp: $(ECC_TB_DIR)/tb_orbit_ecc_bank.v $(ECC_RTL)
	@mkdir -p $(dir $@)
	$(ECC_IVERILOG) -o $@ $^

ecc-sim-bank: $(ECC_OUT)/sim/tb_bank.vvp
	@for s in $(ECC_SIM_SEEDS); do \
	    $(call ECC_RESULT,sim_bank_seed$$s,vvp -n $< +seed=$$s +cycles=$(ECC_SIM_CYCLES) \
	        > $(ECC_OUT)/sim/bank_seed$$s.log 2>&1 && \
	      grep -q '^TB_ORBIT_ECC_BANK PASS' $(ECC_OUT)/sim/bank_seed$$s.log,\
	      $(ECC_SIM_CYCLES) random cycles with upsets (log sim/bank_seed$$s.log)); \
	    sed -n '/summary/,/PASS\|FAIL/p' $(ECC_OUT)/sim/bank_seed$$s.log; \
	done

ecc-sim-quick: $(ECC_OUT)/sim/tb_bank.vvp
	@$(call ECC_RESULT,sim_bank_quick,vvp -n $< +seed=7 +cycles=$(ECC_QUICK_CYCLES) \
	    > $(ECC_OUT)/sim/bank_quick.log 2>&1 && \
	  grep -q '^TB_ORBIT_ECC_BANK PASS' $(ECC_OUT)/sim/bank_quick.log,\
	  $(ECC_QUICK_CYCLES) random cycles with upsets)

# Negative control: every mutant must make at least one bench fail.
ecc-sim-mutants:
	@rm -rf $(ECC_OUT)/mutants && mkdir -p $(ECC_OUT)/mutants
	@$(ECC_PY) $(ECC_TB_DIR)/ecc_mutants.py $(ECC_RTL_DIR) $(ECC_OUT)/mutants $(ECC_MUTANTS) > /dev/null
	@for m in $(ECC_MUTANTS); do \
	    d=$(ECC_OUT)/mutants/$$m; \
	    $(ECC_IVERILOG) -o $$d/codec.vvp $(ECC_TB_DIR)/tb_orbit_secded72.v $$d/orbit_secded72.v && \
	    $(ECC_IVERILOG) -o $$d/bank.vvp $(ECC_TB_DIR)/tb_orbit_ecc_bank.v $$d/orbit_secded72.v \
	        $$d/orbit_ecc_bank.v || exit 1; \
	    vvp -n $$d/codec.vvp > $$d/codec.log 2>&1; \
	    vvp -n $$d/bank.vvp +seed=1 +cycles=$(ECC_MUT_CYCLES) > $$d/bank.log 2>&1; \
	    c=$$(grep -c '^TB_ORBIT_SECDED72 FAIL' $$d/codec.log); \
	    b=$$(grep -c '^TB_ORBIT_ECC_BANK FAIL' $$d/bank.log); \
	    first=$$(grep -h -m1 '^ERROR' $$d/codec.log $$d/bank.log | head -1); \
	    $(call ECC_RESULT,simneg_$$m,[ $$((c + b)) -gt 0 ],\
	      killed (codec bench fail=$$c; bank bench fail=$$b; first: $$first)); \
	done

# ----------------------------------------------------------------------------
# Formal
# ----------------------------------------------------------------------------
ecc-formal: ecc-formal-codec ecc-formal-bank ecc-formal-neg

$(ECC_OUT)/formal/codec/orbit_secded72.sby: $(ECC_FV_DIR)/orbit_secded72.sby $(ECC_CODEC) FORCE_ECC
	@$(call ECC_SBY_GEN,$<,$@,$(ECC_CODEC),$(ECC_BANK))

$(ECC_OUT)/formal/bank/orbit_ecc_bank.sby: $(ECC_FV_DIR)/orbit_ecc_bank.sby $(ECC_RTL) FORCE_ECC
	@$(call ECC_SBY_GEN,$<,$@,$(ECC_CODEC),$(ECC_BANK))

.PHONY: FORCE_ECC
FORCE_ECC:

ecc-formal-codec: $(ECC_OUT)/formal/codec/orbit_secded72.sby
	@mkdir -p $(ECC_RES)
	@$(ECC_RUN_SBY) $< codec PASS $(ECC_FORMAL_TIMEOUT) formal_codec | tee $(ECC_RES)/formal_codec.txt; \
	  exit $${PIPESTATUS[0]}

ecc-formal-clean: $(ECC_OUT)/formal/bank/orbit_ecc_bank.sby
	@mkdir -p $(ECC_RES)
	@$(ECC_RUN_SBY) $< clean PASS $(ECC_FORMAL_TIMEOUT) formal_bank_clean | \
	  tee $(ECC_RES)/formal_bank_clean.txt; exit $${PIPESTATUS[0]}

# Tasks run one after another (each smtbmc prove uses two solver processes).
ecc-formal-bank: $(ECC_OUT)/formal/bank/orbit_ecc_bank.sby
	@mkdir -p $(ECC_RES)
	@fail=0; \
	for t in $(ECC_FV_PASS_TASKS); do \
	    $(ECC_RUN_SBY) $< $$t PASS $(ECC_FORMAL_TIMEOUT) formal_bank_$$t | \
	      tee $(ECC_RES)/formal_bank_$$t.txt; [ $${PIPESTATUS[0]} -eq 0 ] || fail=1; \
	done; \
	for t in $(ECC_FV_FAIL_TASKS); do \
	    $(ECC_RUN_SBY) $< $$t FAIL $(ECC_FORMAL_TIMEOUT) formal_neg_$$t | \
	      tee $(ECC_RES)/formal_neg_$$t.txt; [ $${PIPESTATUS[0]} -eq 0 ] || fail=1; \
	done; \
	exit $$fail

# Negative controls on broken RTL copies: the proofs must FAIL.
ecc-formal-neg:
	@rm -rf $(ECC_OUT)/formal/neg && mkdir -p $(ECC_OUT)/formal/neg $(ECC_RES)
	@$(ECC_PY) $(ECC_TB_DIR)/ecc_mutants.py $(ECC_RTL_DIR) $(ECC_OUT)/formal/neg \
	    codec_even_col bank_no_writeback bank_read_way_swap > /dev/null
	@$(call ECC_SBY_GEN,$(ECC_FV_DIR)/orbit_secded72.sby,$(ECC_OUT)/formal/neg/codec_even_col/orbit_secded72.sby,\
	    $(ECC_OUT)/formal/neg/codec_even_col/orbit_secded72.v,$(ECC_BANK))
	@$(call ECC_SBY_GEN,$(ECC_FV_DIR)/orbit_ecc_bank.sby,$(ECC_OUT)/formal/neg/bank_no_writeback/orbit_ecc_bank.sby,\
	    $(ECC_CODEC),$(ECC_OUT)/formal/neg/bank_no_writeback/orbit_ecc_bank.v)
	@$(call ECC_SBY_GEN,$(ECC_FV_DIR)/orbit_ecc_bank.sby,$(ECC_OUT)/formal/neg/bank_read_way_swap/orbit_ecc_bank.sby,\
	    $(ECC_CODEC),$(ECC_OUT)/formal/neg/bank_read_way_swap/orbit_ecc_bank.v)
	@fail=0; \
	$(ECC_RUN_SBY) $(ECC_OUT)/formal/neg/codec_even_col/orbit_secded72.sby codec FAIL \
	    $(ECC_FORMAL_TIMEOUT) formal_neg_codec_even_col | tee $(ECC_RES)/formal_neg_codec_even_col.txt; \
	[ $${PIPESTATUS[0]} -eq 0 ] || fail=1; \
	$(ECC_RUN_SBY) $(ECC_OUT)/formal/neg/bank_no_writeback/orbit_ecc_bank.sby sec_bmc FAIL \
	    $(ECC_FORMAL_TIMEOUT) formal_neg_bank_no_writeback | tee $(ECC_RES)/formal_neg_bank_no_writeback.txt; \
	[ $${PIPESTATUS[0]} -eq 0 ] || fail=1; \
	$(ECC_RUN_SBY) $(ECC_OUT)/formal/neg/bank_read_way_swap/orbit_ecc_bank.sby sec_bmc FAIL \
	    $(ECC_FORMAL_TIMEOUT) formal_neg_bank_read_way_swap | tee $(ECC_RES)/formal_neg_bank_read_way_swap.txt; \
	[ $${PIPESTATUS[0]} -eq 0 ] || fail=1; \
	exit $$fail

# ----------------------------------------------------------------------------
# Synthesis (generic Yosys cells)
# ----------------------------------------------------------------------------
# Bank flip-flops at the default parameters (DEPTH 16, INTERLEAVE 2, CNT_W 16):
# 16 x 144 array + 4 scrub pointer + 67 read port (valid, data, ce, ue)
# + 32 counters + 7 last-error record = 2414.
ECC_SYNTH_TOPS     := orbit_secded72_enc orbit_secded72_dec orbit_ecc_bank
ECC_SYNTH_BANK_FF  ?= 2414

ecc-synth:
	@mkdir -p $(ECC_OUT)/synth $(ECC_RES)
	@fail=0; \
	for top in $(ECC_SYNTH_TOPS); do \
	    yosys -q -l $(ECC_OUT)/synth/$$top.log -p "read_verilog $(ECC_RTL); \
	        synth -top $$top -flatten; check -assert; \
	        select -assert-none t:\$$dlatch t:\$$_DLATCH_*; delete t:\$$scopeinfo; \
	        tee -o $(ECC_OUT)/synth/$$top.stat stat; tee -o $(ECC_OUT)/synth/$$top.ltp ltp -noff; \
	        write_verilog -noattr $(ECC_OUT)/synth/$$top.v" > /dev/null 2>&1 || { \
	        echo "BAD synth_$$top (yosys failed, log synth/$$top.log)" | tee $(ECC_RES)/synth_$$top.txt; \
	        fail=1; continue; }; \
	    cells=$$(awk '/ cells$$/ {print $$1; exit}' $(ECC_OUT)/synth/$$top.stat); \
	    ffs=$$(awk '/\$$_.*DFF/ {n += $$1} END {print n + 0}' $(ECC_OUT)/synth/$$top.stat); \
	    ltp=$$(sed -n 's/.*length=\([0-9]*\).*/\1/p' $(ECC_OUT)/synth/$$top.ltp); \
	    case $$top in orbit_ecc_bank) want=$(ECC_SYNTH_BANK_FF);; *) want=0;; esac; \
	    if [ "$$ffs" = "$$want" ]; then ok=OK; else ok=BAD; fail=1; fi; \
	    echo "$$ok  synth_$$top cells=$$cells flip-flops=$$ffs (expected $$want) logic depth=$$ltp" | \
	      tee $(ECC_RES)/synth_$$top.txt; \
	done; \
	exit $$fail

# ----------------------------------------------------------------------------
# Report
# ----------------------------------------------------------------------------
ecc-report:
	@if [ "$(abspath $(RTL_DIR))" != "$(abspath rtl)" ]; then \
	    echo "ecc-report: RTL_DIR is not the production rtl/, not writing $(ECC_REPORT_DIR)"; exit 1; fi
	-@$(MAKE) --no-print-directory ecc
	@mkdir -p $(ECC_REPORT_DIR)/logs
	@cp $(ECC_OUT)/summary.txt $(ECC_REPORT_DIR)/results.txt
	@cp $(ECC_OUT)/hsiao.log $(ECC_REPORT_DIR)/logs/
	@for f in $(ECC_OUT)/sim/*.log; do sed -n '/summary/,$$p' $$f > $(ECC_REPORT_DIR)/logs/sim_$$(basename $$f); done
	@for f in $(ECC_OUT)/formal/codec/*.log $(ECC_OUT)/formal/bank/*.log $(ECC_OUT)/formal/neg/*/*.log; do \
	    [ -f $$f ] || continue; \
	    n=$$(echo $$f | sed 's|.*/formal/||; s|/|_|g'); \
	    grep -v -E "Copy '|Treating undriven|engine_0: +[0-9]+ :" $$f | \
	      sed -E 's|[^ [(]*/formal/|formal/|g' | tail -40 > $(ECC_REPORT_DIR)/logs/formal_$$n; \
	done
	@for top in $(ECC_SYNTH_TOPS); do cat $(ECC_OUT)/synth/$$top.stat; done > $(ECC_REPORT_DIR)/synth_stat.txt
	@echo "ecc-report: wrote $(ECC_REPORT_DIR)/"
