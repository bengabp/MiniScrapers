let toggleNewTaskEntry = document.getElementById("new-task-btn");
let tasksContainer = document.getElementById("tasks");
let newTaskEntry = document.getElementById("new-task-entry");
let _screen_width = document.body.clientWidth;
let newTaskButton = document.getElementById("search-btn");
let searchQueryField = document.getElementById("search-query-entry");


let newEntryPbs = document.querySelectorAll("#new-search-settings input[data-tag]");

const baseUrl = "http://20.77.89.95:8000";
const tasksApi = `${baseUrl}/tasks`;

let _newTaskEntryOpen = false;

// Register all event listeners

// Event listener to open/close new task entry
toggleNewTaskEntry.addEventListener("click", (event) => {
	_screen_width = document.body.clientWidth;
	_newTaskEntryOpen = ! _newTaskEntryOpen;
	if (_newTaskEntryOpen){
		if (_screen_width <= 900){
			newTaskEntry.style.transform = 'translateX(0%)';	
		} 
		document.body.style.gridTemplateColumns = "60% 40%";
	} else {
		if (_screen_width <= 900){
			newTaskEntry.style.transform = 'translateX(130%)';
		}
		document.body.style.gridTemplateColumns = "100% 0%";
	}

});

// Window resize
document.body.addEventListener("onresize",(event) => {
	_screen_width = document.body.clientWidth;
	// if (_screen_width <= 900){
	// 	if (_newTaskEntryOpen){
	// 		document.body.style.display = "flex";
	// 		document.body.style.gridTemplateColumns = "100% 0%";
	// 	}
	// } 
	// else {
	// 	newTaskEntry.style.transform = 'translateX(0%)';
	// 	if (_newTaskEntryOpen){

	// 	}
	// 	// newTaskEntry.style.transform = 'translateX(130%)';
	// }
});


// Progress bars in new task entry

newEntryPbs.forEach((newEntryPB) => {
	newEntryPB.addEventListener("input",onNewPBChanged);
});

function onNewPBChanged(event){
	let target = event.target;
	let dataTag = target.attributes["data-tag"].value;
	let progressCount = target.value;
	let targetLabel = document.querySelector(`#new-search-settings span[data-set-label='${dataTag}']`);

	targetLabel.textContent = progressCount;

}

newTaskButton.addEventListener("click",(event) => {
	let searchQuery = searchQueryField.value.trim();
	console.log("Button clicked !")

	if (searchQuery.length <= 2){
		alert("Search query must be more than 2 characters !");
		return
	}

	let taskDetails = {
		"search_q": searchQuery
	};

	document.querySelectorAll("#new-search-settings input[data-tag]").forEach((element) => {
		let dataTag = element.attributes["data-tag"].value;
		let progressCount = element.value;
		taskDetails[dataTag] = parseInt(progressCount);
	});

	fetch(tasksApi, {
		method: "POST",
		headers:{"Content-Type":"application/json"},
		body: JSON.stringify(taskDetails),
		redirect: 'follow'
	})
	  .then(async response => await response)
	  .then(async (result) => {
	  	let jsonResult = await result.json();
	  	let status = jsonResult.status;
	  	if (status == "success"){
	  		let taskId = jsonResult.task_id;
	  		let taskState = "RUNNING";
	  		let new_task = 
	  			`
		  			<div class="task" data-testid="${taskId}">
	                    <div class="task-header">
	                        <div>
	                            <span class="q">${searchQuery}</span>
	                            <span class="status-tag task-status-${taskState.toLowerCase()}">${taskState}</span>
	                        </div>
	                        <div>
	                            <div>
	                                <i class="fa-regular fa-clock"></i>
	                                <span>1m ago</span>
	                            </div>
//	                            <button class="action-btn download-btn floating-btn">
//	                                <i class="fa-solid fa-download"></i>
//	                            </button>
	                            <button class="action-btn delete-btn floating-btn">
	                                <i class="fa-regular fa-trash-can"></i>
	                            </button>
	                        </div>
	                    </div>
	                    <div class="task-settings-wrap">
	                        <div>
	                            <i class="fa-regular fa-comment"></i>
	                            <span>${taskDetails.comments}</span>
	                        </div>
	                        <div>
	                            <i class="fa-regular fa-thumbs-up"></i>
	                            <span>${taskDetails.likes}</span>
	                        </div>
	                        <div>
	                            <i class="fa-solid fa-repeat"></i>
	                            <span>${taskDetails.retweets}</span>
	                        </div>
	                    </div>
	                </div>

	  			`
	  		tasksContainer.insertAdjacentHTML("afterbegin",new_task);
	  	}

	  })
	  .catch(error => console.log('error', error));


});

console.log("Javascript connected !")

fetch(tasksApi)
	.then(async response => await response)
	.then(async result => {
		let apiResult = await result.json();
		let allTasks = apiResult.tasks;
		if (allTasks){
			allTasks.forEach((task) => {
		  		let taskId = task.crawler_id;
		  		let taskState = task.stats.state;
		  		let searchq = task.query.q;
		  		let m_retweets = task.query.retweet_usernames_per_tweet;
		  		let m_likes = task.like_usernames_per_tweet;
		  		let m_comments = task.comment_usernames_per_tweet;
		  		let downloadLink = task.result.download_link
		  		let new_task = 
		  			`
			  			<div class="task" data-testid="${taskId}">
		                    <div class="task-header">
		                        <div>
		                            <span class="q">${searchq}</span>
		                            <span class="status-tag task-status-${taskState.toLowerCase()}">${taskState}</span>
		                        </div>
		                        <div>
		                            <div>
		                                <i class="fa-regular fa-clock"></i>
		                                <span>1m ago</span>
		                            </div>
		                            <button class="action-btn download-btn floating-btn">
		                                <i class="fa-solid fa-download"></i>
		                            </button>
		                            <button class="action-btn delete-btn floating-btn">
		                                <i class="fa-regular fa-trash-can"></i>
		                            </button>
		                        </div>
		                    </div>
		                    <div class="task-settings-wrap">
		                        <div>
		                            <i class="fa-regular fa-comment"></i>
		                            <span>5</span>
		                        </div>
		                        <div>
		                            <i class="fa-regular fa-thumbs-up"></i>
		                            <span>600</span>
		                        </div>
		                        <div>
		                            <i class="fa-solid fa-repeat"></i>
		                            <span>459</span>
		                        </div>
		                    </div>
		                </div>

		  			`
		  		tasksContainer.insertAdjacentHTML("afterbegin",new_task);
		});
	}	
	console.log(allTasks)
});
