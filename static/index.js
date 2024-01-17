$(document).ready(function(){
    $("#send-ajax-request").click(function(){
      $.ajax({
        url: "/chat", 
        type: "POST", 
        data: {
          enteredText: $(".chat-input").val()
        },
        success: function(response) {
          $("#responding_container").html(response);
        },
        error: function(xhr, status, error) {
          console.error("AJAX request failed:", status, error);
        }
      });
    });
  });
  /*COLOR CHANGING*/
  document.addEventListener('DOMContentLoaded', function () {
    const buttons = document.querySelectorAll('#red, #blue, #yellow, #purple');
  
    buttons.forEach(button => {
      button.addEventListener('click', function () {
        this.classList.toggle('clicked');
        console.log(this.innerText);
        //check if inner text in category_filterr if not add it in if yes remove it
        if (category_filterr.includes(this.innerText)) {
          category_filterr = category_filterr.filter(item => item !== this.innerText);
        } else {
          category_filterr.push(this.innerText);
        }
        render_log_lines();
      });
    });
  });
  document.addEventListener('DOMContentLoaded', function () {
    const scrollableItems = document.querySelectorAll('.scrollable-item');

    function toggleClickedClass() {
      this.classList.toggle('clicked');
       //same thing for program_filterr
       if (program_filterr.includes(this.innerText)) {
        program_filterr = program_filterr.filter(item => item !== this.innerText);
      } else {
        program_filterr.push(this.innerText);
      }
      render_log_lines();
    }

    scrollableItems.forEach(item => {
      item.addEventListener('click', toggleClickedClass);
    });
  });
  
//render log lines
$(document).ready(function(){
    //send chat
    $("#removeChat").click(function(){
        $.ajax({
          url: "/remove-chat-history", 
          type: "GET", 
          success: function(response) {
            var chatOutput = $('#chatOutput');
            chatOutput.empty();
          },
          error: function(xhr, status, error) {
            console.error("AJAX request failed:", status, error);
          }
        });
      });

      $('.example-message').click(function() {
        var messageText = $(this).text();
        $('#chatInput').val(messageText);
    });


      $('#sendButton').click(function() {
        var message = $('#chatInput').val();
        $('#chatInput').val('');
    
        if (!message.trim()) {
            return;
        }
    
        // Streaming response
        var chatOutput = $('#chatOutput');

        let send_heatmap = true;
        let old_html = chatOutput.html();
        chatOutput.html(old_html + `
              <div class="user message">${message}</div>`);
        var xhr = new XMLHttpRequest();
        xhr.open('POST', '/send-chat', true);
        xhr.setRequestHeader('Content-Type', 'application/json');
        xhr.onreadystatechange = function() {
          

            if(xhr.readyState === XMLHttpRequest.LOADING) {
              chatOutput.html(old_html + `
              <div class="user message">${message}</div>
              <div class="ai message">${xhr.responseText}</div>`);
              //autoscroll chatoutput
              chatOutput.scrollTop(chatOutput[0].scrollHeight);

              if (send_heatmap) {
                fetchHeatmap();
                send_heatmap = false;
              }
            } else if (xhr.readyState === XMLHttpRequest.DONE) {
                fetchChatHistory();
            }
        };
        var highlightedText = $('.line.user_highlighted').map(function() {
            return $(this).text();
        }).get().join(' ');
        xhr.send(JSON.stringify({ message: message,context:highlightedText }));
    });
    
    function fetchChatHistory() {
        $.ajax({
            url: '/get-chat-history',
            type: 'GET',
            success: function(response) {
              console.log(response);
                $('#chatOutput').empty();
                updateChat(response);
            }
        });
    }


    function fetchHeatmap() {
        $.ajax({
            url: '/get-heatmap',
            type: 'GET',
            success: function(response) {
                var gradient = response.gradient;
                $('.heatmapgradient').css('background', gradient);
                response.underline.forEach(function(line) {
                  //set backround color of line 
                  $('#line' + line).css('background', "#ffff003d");
                });
            },
            error: function(error) {
                console.log(error);
            }
        });
    }

  // Function to update chat interface
  function updateChat(messages) {
      var chatOutput = $('#chatOutput');
      chatOutput.empty();
      let html = '';
      messages.forEach(function(msg) {
        let role = msg.role;
        if (role == 'assistant') role = "ai";
        html = `<div class="${role} message">${msg.content}</div>`;
          chatOutput.append(html);
      });
  }


  // Initial load of chat history
  fetchChatHistory();


});



//dragging selection shit
let isDragging = false;
let highlightedDivs = new Set(); // To track highlighted divs
$(document).on({
  'mousemove': function(e) {
      if (!isDragging) return;
      $('.line').each(function() {
          if (elementInDragArea($(this), e)) {
              $(this).addClass('highlighted');
              highlightedDivs.add(this.id);
          } else {
              $(this).removeClass('highlighted');
              highlightedDivs.delete(this.id);
          }
      });

      // Limit logic goes here
  },
  'mousedown': function(e) {
      isDragging = true;
      highlightedDivs.clear();
  },
  'mouseup': function(e) {
      isDragging = false;
      console.log(highlightedDivs);
      if (highlightedDivs.size != 0) {
        window.getSelection().removeAllRanges();
        //remove old user_highlighted
        $('.line.user_highlighted').removeClass('user_highlighted');

        highlightedDivs.forEach(function(div) {
            $("#"+div).addClass('user_highlighted');
        });
      }
      // Process highlightedDivs here
      //iterate over highlightedDivs and change their background color to blue
      
  }
});

let dragStartX = 0;
let dragStartY = 0;

document.addEventListener('mousedown', function(e) {
    isDragging = true;
    dragStartX = e.pageX; // Record the starting X position of the drag
    dragStartY = e.pageY; // Record the starting Y position of the drag
    highlightedDivs.clear();
});

function elementInDragArea(element, mouseEvent) {
    // Convert element to a DOM element if necessary
    if (element.jquery) {
        element = element[0];
    }
    if (typeof element === 'string') {
        element = document.getElementById(element);
    }
    if (!(element instanceof HTMLElement)) {
        console.error('Invalid element passed to elementInDragArea');
        return false;
    }

    const rect = element.getBoundingClientRect();
    const topBoundary = Math.min(dragStartY, mouseEvent.pageY);
    const bottomBoundary = Math.max(dragStartY, mouseEvent.pageY);
    const leftBoundary = Math.min(dragStartX, mouseEvent.pageX);
    const rightBoundary = Math.max(dragStartX, mouseEvent.pageX);

    return rect.top + window.scrollY < bottomBoundary && rect.bottom + window.scrollY > topBoundary &&
           rect.left + window.scrollX < rightBoundary && rect.right + window.scrollX > leftBoundary;
}