#!/bin/sh
# =======================================================================================
# This script submits all three phases (ADSP, RGSP, TRANS) with SLURM dependencies
# so they run automatically in sequence without manual intervention.
# =======================================================================================

casenumber=2

#Modified CNP parameter file fsoilordercon with r_desorp[Gelisols=2] increased 10× (0.00022 → 0.0022) 
#with python script: ~/Desktop/Work/NGEE-Arctic/Kougarok/Program/fates_parameter_modification/modify_cnp_parameters.py
#fsoilorderconfile='CNP_parameters_c180312_Gelisols_rdesorp2x'
fsoilorderconfile='CNP_parameters_c180312'

testcase='' #added in case name
testpara='' #added in fates_paramfile name

# Which phases to run (you can comment out phases you don't need)
RUN_PHASES=("ADSP" "RGSP" "TRANS")

cd ~/E3SM_FATES/cime/scripts
pwd=`pwd`
rpwd=`readlink -f $pwd`
CREATE_NEWCASE_COMMAND=`sed "s/\/global\//\/dvs_ro\//g" <<< $rpwd`"/create_newcase"

Script_NAME=Kougarok_ELM-FATES_PtCNPEn${casenumber}
CIME_OUTPUT_ROOT=~/Kougarok_PlantTraitsCNPEnsemble162_Morris_RGSPsuplP/

DIN_LOC_ROOT=/dvs_ro/cfs/cdirs/e3sm/inputdata/
DIN_LOC_ROOT_CLMFORC=$DIN_LOC_ROOT/atm/datm7

MACH=pm-cpu
PROJECT=m2467
COMPILER=intel

CIME_MODEL=e3sm
SITE_NAME=koug
ELM_USRDAT_DOMAIN=domain_Kougarok_from0.125x0.125_simyr1850_c240309.nc
ELM_USRDAT_SURDAT=surfdata_Kougarok_from0.125x0.125_simyr1850_c240309_ModPval.nc
RES=ELM_USRDAT

ELM_SURFDAT_DIR=/dvs_ro/u1/j/jingtao/CaseScripts/Kougarok_FATES
ELM_DOMAIN_DIR=/dvs_ro/u1/j/jingtao/CaseScripts/Kougarok_FATES

ELM_HASH=`(cd ../../components;git log -n 1 --pretty=%h)`
FATES_HASH=`(cd ../../components/elm/src/external_models/fates;git log -n 1 --pretty=%h)`
GIT_HASH=E${ELM_HASH}-F${FATES_HASH}

# Array to store job IDs
declare -A JOB_IDS

# Function to create and setup a case for a given phase
create_phase_case() {
    local PHASE=$1

    echo "========================================"
    echo "Setting up phase: $PHASE"
    echo "========================================"

    CASE_NAME=$Script_NAME$testcase\_$PHASE

    # Set COMPSET based on phase
    if [ $PHASE = 'ADSP' ] || [ $PHASE = 'RGSP' ]; then
        COMPSET=1850_DATM%QIA_ELM%BGC-FATES_SICE_SOCN_SROF_SGLC_SWAV
    fi
    if [ $PHASE = 'TRANS' ]; then
        COMPSET=2000_DATM%QIA_ELM%BGC-FATES_SICE_SOCN_SROF_SGLC_SWAV
    fi

    # Ensure we're in the scripts directory before creating the case
    cd ~/E3SM_FATES/cime/scripts

    rm -rf $CASE_NAME
    rm -rf $CIME_OUTPUT_ROOT$CASE_NAME

    # CREATE THE CASE
    $CREATE_NEWCASE_COMMAND -case $CASE_NAME -res $RES -compset $COMPSET -mach $MACH -project $PROJECT -compiler $COMPILER
    
    cd ${CASE_NAME}

    # SET PATHS
    ./xmlchange CIME_OUTPUT_ROOT=$CIME_OUTPUT_ROOT
    ./xmlchange DIN_LOC_ROOT=$DIN_LOC_ROOT
    ./xmlchange DIN_LOC_ROOT_CLMFORC=$DIN_LOC_ROOT_CLMFORC

    ./xmlchange ATM_DOMAIN_FILE=${ELM_USRDAT_DOMAIN}
    ./xmlchange ATM_DOMAIN_PATH=${ELM_DOMAIN_DIR}
    ./xmlchange LND_DOMAIN_FILE=${ELM_USRDAT_DOMAIN}
    ./xmlchange LND_DOMAIN_PATH=${ELM_DOMAIN_DIR}
    ./xmlchange DATM_MODE=CLMGSWP3v1
    ./xmlchange ELM_USRDAT_NAME=${SITE_NAME}

    ./xmlchange NTASKS=1
    ./xmlchange ATM_GRID=ELM_USRDAT
    ./xmlchange LND_GRID=ELM_USRDAT

    ./xmlchange --append ELM_BLDNML_OPTS="-nutrient cnp -nutrient_comp_pathway eca -soil_decomp century"

    ./xmlchange DEBUG=FALSE
    ./xmlchange STOP_OPTION=nyears
    ./xmlchange REST_OPTION=nyears

    # Phase-specific settings
    if [ $PHASE = 'ADSP' ]; then
        ./xmlchange --append ELM_BLDNML_OPTS="-bgc_spinup on"
        ./xmlchange STOP_N=200
        ./xmlchange REST_N=10
        ./xmlchange RUN_STARTDATE='0001-01-01'
        ./xmlchange DATM_CLMNCEP_YR_START=1901
        ./xmlchange DATM_CLMNCEP_YR_END=1920
        RESTART_FILE=""
    fi

    if [ $PHASE = 'RGSP' ]; then
        ./xmlchange STOP_N=200
        ./xmlchange REST_N=10
        ./xmlchange RUN_STARTDATE='0201-01-01'
        ./xmlchange DATM_CLMNCEP_YR_START=1901
        ./xmlchange DATM_CLMNCEP_YR_END=1920
        restart_yearstr=0201
        rstCASE_NAME=$Script_NAME$testcase\_ADSP
        RESTART_FILE="${CIME_OUTPUT_ROOT}${rstCASE_NAME}/run/${rstCASE_NAME}.elm.r.${restart_yearstr}-01-01-00000.nc"
    fi

    if [ $PHASE = 'TRANS' ]; then
        ./xmlchange STOP_N=119
        ./xmlchange REST_N=1
        ./xmlchange RUN_STARTDATE='1901-01-01'
        ./xmlchange DATM_CLMNCEP_YR_START=1901
        ./xmlchange DATM_CLMNCEP_YR_END=2019
        restart_yearstr=0401
        rstCASE_NAME=$Script_NAME$testcase\_RGSP
        RESTART_FILE="${CIME_OUTPUT_ROOT}${rstCASE_NAME}/run/${rstCASE_NAME}.elm.r.${restart_yearstr}-01-01-00000.nc"
    fi

    ./xmlchange JOB_WALLCLOCK_TIME=47:59:00
    ./xmlchange EXEROOT=${CIME_OUTPUT_ROOT}/Kougarok_ELM-FATES_PtCNPEn1_$PHASE\/bld
    ./xmlchange BUILD_COMPLETE=TRUE

    ./xmlchange GMAKE=make

    # MODIFY THE ELM NAMELIST
    cat >> user_nl_elm <<EOF
        hist_mfilt = 12
        hist_nhtfrq = 0
        fsurdat = '${ELM_SURFDAT_DIR}/${ELM_USRDAT_SURDAT}'

        use_fates=.true.
        fates_parteh_mode = 2
        use_fates_nocomp = .false.
        fates_paramfile = '/dvs_ro/u1/j/jingtao/E3SM_Aid/FATES-ParameterFiles/fates_params_NonPrescribed_EnPlantTraitsCNPparam162_Morris/fates_params_api25.5.0_12pft_c230710__PtCNP162_En${casenumber}${testpara}.nc'
        fsoilordercon = '~/E3SM_Aid/clm_params/${fsoilorderconfile}.nc'
        hist_fincl1='FATES_VEGC_ABOVEGROUND_SZPF','FATES_VEGC_SZPF','FATES_VEGN_SZPF','FATES_VEGP_SZPF','FATES_STOREN_TF_CANOPY_SZPF','FATES_STOREN_TF_USTORY_SZPF','FATES_STOREP_TF_CANOPY_SZPF','FATES_STOREP_TF_USTORY_SZPF','FATES_NH4UPTAKE_SZPF','FATES_NO3UPTAKE_SZPF','FATES_PUPTAKE_SZPF','FATES_NEFFLUX_SZPF','FATES_DDBH_CANOPY_SZPF','FATES_DDBH_USTORY_SZPF','FATES_PEFFLUX_SZPF','FATES_NFIX_SYM_SZPF','FATES_NPP_SZPF','FATES_STOREC_TF_CANOPY_SZPF','FATES_STOREC_TF_USTORY_SZPF','FATES_FROOTCTURN_USTORY_SZ','FATES_FROOTCTURN_CANOPY_SZ','FATES_NDEMAND_SZPF','FATES_PDEMAND_SZPF','FATES_LEAFC_SZPF', 'FATES_LEAFN_SZPF','FATES_LEAFP_SZPF','FATES_FROOTC_SZPF','FATES_FROOTN_SZPF','FATES_FROOTP_SZPF','FATES_REPROC_SZPF','FATES_REPRON_SZPF', 'FATES_REPROP_SZPF','FATES_SAPWOODC_SZPF','FATES_SAPWOODN_SZPF','FATES_SAPWOODP_SZPF','FATES_STOREC_SZPF','FATES_STOREN_SZPF','FATES_STOREP_SZPF','FATES_LEAF_ALLOC_SZPF','FATES_SEED_ALLOC_SZPF','FATES_STEM_ALLOC','FATES_FROOT_ALLOC_SZPF','FATES_CROOT_ALLOC','FATES_STORE_ALLOC','FATES_DDBH_SZPF','FATES_BASALAREA_SZPF'
EOF

    if [ "$PHASE" = 'ADSP' ]; then
        echo 'suplphos = '\'ALL\' >> user_nl_elm
        echo 'suplnitro = '\'NONE\' >> user_nl_elm
        echo 'finidat = '\'\' >> user_nl_elm
        echo 'nyears_ad_carbon_only = 30' >> user_nl_elm
    elif [ "$PHASE" = 'RGSP' ]; then
        echo 'suplphos = '\'ALL\' >> user_nl_elm
        echo 'suplnitro = '\'NONE\' >> user_nl_elm
        echo "finidat = '${RESTART_FILE}'" >> user_nl_elm
    elif [ "$PHASE" = 'TRANS' ]; then
        echo 'suplphos = '\'NONE\' >> user_nl_elm
        echo 'suplnitro = '\'NONE\' >> user_nl_elm
        echo "finidat = '${RESTART_FILE}'" >> user_nl_elm
    fi

    cat <<EOF > ./user_nl_mosart
        do_rtm = .false.
    EOF

    cat >> user_nl_datm <<EOF
        taxmode = "cycle", "cycle", "cycle","extend"
EOF

    cp ~/E3SM_Aid/RedirectForcing/atm_forcing.datm7.GSWP3-w5e5.c211106/user_datm.streams.txt* ./

    ./case.setup
    
    ./preview_namelists

    #./case.build
    
    # Create placeholder restart files for RGSP/TRANS so CIME's input data check passes at submission time.
    # The real restart files will exist by the time the dependent jobs actually run.
    if [ -n "$RESTART_FILE" ]; then
        mkdir -p "$(dirname "$RESTART_FILE")"
        touch "$RESTART_FILE"
    else
        echo "No restart file to create placeholder for"
    fi
    
}

# Create all phases first
# Then Navigate to case directory and submit with dependency

submit_phase_case() {
    local PHASE=$1
    local DEPEND_JOBID=$2

    CASE_NAME=$Script_NAME$testcase\_$PHASE

    cd ~/E3SM_FATES/cime/scripts/${CASE_NAME}

    # Submit with dependency if applicable
    if [ -z "$DEPEND_JOBID" ]; then
        # No dependency - first phase
        SUBMIT_OUTPUT=$(./case.submit --batch-args="-q shared --mem=8G --mail-type=ALL --mail-user=tjmuse@gmail.com" 2>&1)
    else
        # With dependency on previous phase
        SUBMIT_OUTPUT=$(./case.submit --batch-args="-q shared --mem=8G --mail-type=ALL --mail-user=tjmuse@gmail.com --dependency=afterok:$DEPEND_JOBID" 2>&1)
    fi

    # Show submission output (to stderr so it doesn't pollute return value)
    echo "$SUBMIT_OUTPUT" >&2

    # Extract job ID - matches "Submitted job id is XXXX" or "with id XXXX"
    JOBID=$(echo "$SUBMIT_OUTPUT" | grep -oP '(?:Submitted job id is |with id )\K[0-9]+' | head -1 || echo "")
    if [ -z "$JOBID" ]; then
        # Try alternative method using squeue
        sleep 2
        JOBID=$(squeue -u $USER -n $CASE_NAME -h -o "%i" | head -1)
    fi

    if [ -n "$JOBID" ]; then
        if [ -z "$DEPEND_JOBID" ]; then
            echo "Phase $PHASE submitted with job ID: $JOBID" >&2
        else
            echo "Phase $PHASE submitted with job ID: $JOBID (depends on $DEPEND_JOBID)" >&2
        fi
    else
        echo "Warning: Could not extract job ID for $PHASE" >&2
    fi

    cd ..

    # Only output the job ID to stdout (for capture by caller)
    echo "$JOBID"
}

# Main execution loop
PREV_JOBID=""

# First, create all phase cases
for PHASE in "${RUN_PHASES[@]}"; do
    create_phase_case $PHASE
done

# Then, submit all phases with dependencies
for PHASE in "${RUN_PHASES[@]}"; do
    JOBID=$(submit_phase_case $PHASE $PREV_JOBID)
    PREV_JOBID=$JOBID
    JOB_IDS[$PHASE]=$JOBID
    echo ""
done

echo "========================================"
echo "All phases submitted!"
echo "========================================"
for PHASE in "${RUN_PHASES[@]}"; do
    if [ -n "${JOB_IDS[$PHASE]}" ]; then
        echo "$PHASE: Job ID ${JOB_IDS[$PHASE]}"
    fi
done
echo ""
echo "Monitor progress with: squeue -u $USER"
echo "========================================"
