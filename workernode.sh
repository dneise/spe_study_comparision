#!/bin/bash
export PATH=/usr/java/jdk1.8.0_77/bin:$PATH

echo "USER: $USER"
echo "JOB_ID: $JOB_ID"
echo "JOB_NAME: $JOB_NAME"
echo "HOSTNAME: $HOSTNAME"

export temp_dir_base=/tmp/dneise_facttools_
export temp_dir=$temp_dir_base$JOB_ID

# delete folders like temp_dir_base with a number smaller than 

find . -name "$temp_dir_base*" | while read file; do 
  [ "${file#$temp_dir_base}" -lt 4434318 ] && rm -rfv "$file" 
  done

echo "java \
   -XX:MaxHeapSize=1024m \
   -XX:InitialHeapSize=512m \
   -XX:CompressedClassSpaceSize=64m \
   -XX:MaxMetaspaceSize=128m \
   -XX:+UseConcMarkSweepGC \
   -XX:+UseParNewGC \
   -jar $jar_path \
    $xml_path \
    -Dinfile=$infile \
    -Doutput=$temp_dir/$basename \
    -Ddrsfile=$drsfile \
    -DauxFolder=$auxFolder"


mkdir -p $temp_dir

# outdir:  wo es spaeter hinsoll
# basename: der basename ebven
start_time=`date -Is`

java \
   -XX:MaxHeapSize=1024m \
   -XX:InitialHeapSize=512m \
   -XX:CompressedClassSpaceSize=64m \
   -XX:MaxMetaspaceSize=128m \
   -XX:+UseConcMarkSweepGC \
   -XX:+UseParNewGC \
   -jar $jar_path \
    $xml_path \
    -Dinfile=$infile \
    -Doutput=$temp_dir/$basename \
    -Ddrsfile=$drsfile \
    -DauxFolder=$auxFolder 

mkdir -p $outdir
cp $temp_dir/* $outdir/.
rm -rf $temp_dir

end_time=`date -Is`
echo "{\"job_id\": \"$JOB_ID\", \"start_time\": \"$start_time\", \"end_time\": \"$end_time\"}"

