#~/usr/bin/bash

fdir="./updated_runs/bias_dphi1/"

xmin=-10
xmax=10
dx=0.5

# per channel
for ((j=1; j<=6; j++))
do 
    for k in {0..40}
    do
        x1=$(echo "scale=3; $xmin+$k*$dx" | bc)
        sed "s/dphi1\_$j: \['dphi1', 'fixed', \[0.\]\]/dphi1\_$j: \['dphi1', 'fixed', \[$x1\]\]/" $fdir"config.yml" > $fdir"runconfig.yml"
        /mnt/zfsusers/mabitbol/.local/lib/python3.6/site-packages/bbpipe $fdir"settings.yml"
        cp $fdir"output/sampler_out.npz" $fdir"autoresults/perchannel_eb_dphi1"$j"_$x1.npz"
    done
done

for j in 1 3 5
do 
    jj=$((j+1))

    for k in {0..40}
    do
        # symmetric
        x1=$(echo "scale=3; $xmin+$k*$dx" | bc)
        sed "s/dphi1\_$j: \['dphi1', 'fixed', \[0.\]\]/dphi1\_$j: \['dphi1', 'fixed', \[$x1\]\]/" $fdir"config.yml" > $fdir"runconfig.yml"
        sed -i "s/dphi1\_$jj: \['dphi1', 'fixed', \[0.\]\]/dphi1\_$jj: \['dphi1', 'fixed', \[$x1\]\]/" $fdir"runconfig.yml"
        /mnt/zfsusers/mabitbol/.local/lib/python3.6/site-packages/bbpipe $fdir"settings.yml"
        cp $fdir"output/sampler_out.npz" $fdir"autoresults/symmetric_eb_dphi1"$j$jj"_$x1.npz"

        # asymmetric
        x2=$(echo "scale=3; $xmax-$k*$dx" | bc)
        sed "s/dphi1\_$j: \['dphi1', 'fixed', \[0.\]\]/dphi1\_$j: \['dphi1', 'fixed', \[$x1\]\]/" $fdir"config.yml" > $fdir"runconfig.yml"
        sed -i "s/dphi1\_$jj: \['dphi1', 'fixed', \[0.\]\]/dphi1\_$jj: \['dphi1', 'fixed', \[$x2\]\]/" $fdir"runconfig.yml"
        /mnt/zfsusers/mabitbol/.local/lib/python3.6/site-packages/bbpipe $fdir"settings.yml"
        cp $fdir"output/sampler_out.npz" $fdir"autoresults/asymmetric_eb_dphi1"$j$jj"_"$x1"_"$x2".npz"
    done
done

