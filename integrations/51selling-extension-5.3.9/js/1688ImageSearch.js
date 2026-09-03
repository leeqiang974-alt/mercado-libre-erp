//获取加密时间
function GetEncryptionTime() {
    //$.ajax({
    //    url: config.aliUrl.encryptionTime(),
    //    type: 'get',
    //    dataType: 'json',
    //    data: "",
    //    async: false,
    //    cache: false,
    //    //headers: {
    //    //    'Access-Control-Allow-Origin': "*"
    //    //},
    //    success: function (res) {
    //        if (res !== null) {
    //            if (res["cbu.searchweb.config.system.currenttime"].code == "200") {
    //                GetSign(res["cbu.searchweb.config.system.currenttime"].dataSet);
    //            } else {
    //            }
    //        } else {
    //        }
    //    },
    //    error: function (e) {
    //        result = 404;
    //    }
    //});
}


function GetSign(dataSet) {
    var appName = "pc_tusou";
    var appKey = btoa(appName + ";" + dataSet);

}

function UploadImgToOss(filePath, appName, appKey) {

}