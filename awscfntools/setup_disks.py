import shutil
import os
import boto3
import json
import ec2_metadata
import subprocess

def format_disk(dev,type):
    print(dev,type)
    try:
        result = subprocess.run(['sudo','mkfs','-t',type,dev],capture_output=True, text=True, check=True)
        return(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"Error executing mkfs {e}")
    except FileNotFoundError:
        print("mkfsnot found. Please install it.")

def list_drive_info():
    try:
        result = subprocess.run(['lsblk','-l','-N','--json','-o','+UUID,FSTYPE'],capture_output=True, text=True, check=True)
        return json.loads(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"Error executing lsblk {e}")
    except FileNotFoundError:
        print("lsblk found. Please install it.")

def main():
    client = boto3.client("ec2",region_name=ec2_metadata.ec2_metadata.region)
    response = client.describe_volumes(Filters=[{"Name":"attachment.instance-id","Values":[ec2_metadata.ec2_metadata.instance_id]}])
    mounts = {}
    for v in response["Volumes"]:
        tags = dict([(i["Key"],i["Value"]) for i in v.get("Tags",[])])
        if tags.get("mountpoint",None):
            #print(tags.get("mountpoint",""),v["VolumeId"])
            volid = v["VolumeId"].replace("-","")
            mounts[volid] = {"mount":tags.get("mountpoint",""),"fstype":tags.get("fstype","ext4"),"owner":tags.get("owner","root:root")}
            try:
                os.mkdir(tags["mountpoint"])
                user, group = tags["owner"].split(":")
                print("Setting ownership of {mnt} to {user}:{group}".format(mnt=tags["mountpoint"],user=user,group=group))
                shutil.chown(tags["mountpoint"],user=user,group=group)
            except Exception as e:
                print(f"Error mkdir {e}")

    devices = list_drive_info()
    for i in devices["blockdevices"]:
        mntinfo = mounts.get(i["serial"],None)
        if mntinfo:
            dev = "/dev/"+i["name"]
            print(dev,i["fstype"])
            if not i["fstype"]:
                print("NOT FORMATED - Formatting...",i["name"],dev)
                format_disk(dev,mntinfo["fstype"])
            else:
                print("ALREADY FORMATTED",i["name"]);

    devices = list_drive_info() # reload after formatting
    with open("/etc/fstab","a") as file:
        for i in devices["blockdevices"]:
            mntinfo = mounts.get(i["serial"],None)
            if mntinfo:
                if i["uuid"] is not None:
                    dev = "/dev/"+i["name"]
                    print("UUID={uuid} {mountpoint} {fstype} discard,commit=30,errors=remount-ro    0 1".format(uuid=i["uuid"],fstype=mntinfo["fstype"],mountpoint=mntinfo["mount"]),file=file)

if __name__ == '__main__':
    main()
