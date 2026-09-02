//发送消息到contentscript
function sendMessageToContentScript(message, tab, callback) {
	chrome.tabs.query({ active: true, currentWindow: true }, function (tabs) {
		chrome.tabs.sendMessage(tab.id, message, function (response) {
			if (callback) callback(response);
			return true;
		});
	});
}

//发送消息到backgroundscript
function sendMessageToBackgroudScript(message, callback) {
	chrome.runtime.sendMessage(message, function (response) {
		if (callback) callback(response);
		return true;
	});
}