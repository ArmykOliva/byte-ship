//render log lines
let log_lines = [];
let categories = ["debug","info","warning","error"];
let category_filterr = [];
let program_filterr = [];


function render_log_lines(category_filter=category_filterr, program_filter=program_filterr) {
    let container = $('#log-viewer');
    container.empty();
    log_lines.forEach(function(line, index) {
        if (category_filter.length > 0 && !category_filter.includes(line.category.toLowerCase())) {
            return;
        }
        if (program_filter.length > 0 && !program_filter.includes(line.program.toLowerCase())) {
            return;
        }
        let lineContent = `
            <div class="line" id='line${index+1}'>
                <div class="line-num">${index + 1}</div>
                <pre> <em>${line.timestamp || ''}</em> <strong>${line.program}</strong> - ${line.message} </pre>
            </div>`;
        container.append(lineContent);
    });
}

$(document).ready(function(){
    $.ajax({
        url: '/get-log-lines',
        type: 'GET',
        success: function(response){
            log_lines = response;
            render_log_lines();
        }
    });
});