// Custom JavaScript for Cricket Tournament Management System

$(document).ready(function() {
    // Initialize tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'))
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl)
    });

    // Auto-hide alerts after 5 seconds
    setTimeout(function() {
        $('.alert').fadeOut('slow');
    }, 5000);

    // Form validation
    $('form').on('submit', function() {
        $(this).find('button[type="submit"]').prop('disabled', true);
    });

    // Dynamic player search
    $('#playerSearch').on('keyup', function() {
        var searchText = $(this).val().toLowerCase();
        $('.player-item').each(function() {
            var playerName = $(this).find('.player-name').text().toLowerCase();
            if(playerName.indexOf(searchText) !== -1) {
                $(this).show();
            } else {
                $(this).hide();
            }
        });
    });
});

// Function to calculate player statistics
function calculatePlayerStats(playerId) {
    $.ajax({
        url: '/api/player_stats/' + playerId,
        method: 'GET',
        success: function(data) {
            $('#batting-avg').text(data.batting_avg);
            $('#bowling-avg').text(data.bowling_avg);
            $('#strike-rate').text(data.strike_rate);
            $('#economy').text(data.economy);
        }
    });
}

// Function to update match score
function updateMatchScore(matchId, innings, data) {
    $.ajax({
        url: '/api/update_score/' + matchId,
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify(data),
        success: function(response) {
            if(response.success) {
                $('#score-' + innings).addClass('score-updated');
                setTimeout(function() {
                    $('#score-' + innings).removeClass('score-updated');
                }, 2000);
                updateScoreboard(matchId);
            }
        }
    });
}

// Function to refresh scoreboard
function updateScoreboard(matchId) {
    $.ajax({
        url: '/api/scoreboard/' + matchId,
        method: 'GET',
        success: function(data) {
            $('#scoreboard-content').html(data);
        }
    });
}

// Function to confirm deletion
function confirmDelete(message) {
    return confirm(message || 'Are you sure you want to delete this item?');
}

// Function to format currency
function formatCurrency(amount) {
    return '₹' + (amount/100000).toFixed(2) + 'L';
}

// Function to calculate net run rate
function calculateNRR(runsScored, oversFaced, runsConceded, oversBowled) {
    var runRate = runsScored / oversFaced;
    var concededRate = runsConceded / oversBowled;
    return (runRate - concededRate).toFixed(2);
}