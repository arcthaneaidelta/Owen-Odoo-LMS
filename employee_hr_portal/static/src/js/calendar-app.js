/** @odoo-module **/
document.addEventListener('DOMContentLoaded', function() {
    if (!document.getElementById('calendarDays')) return;
	// Current date
	const today = new Date();
	let currentDate = new Date(today);
	let selectedDate = new Date(today);
	let modalCustomYear = currentDate.getFullYear();
	let currentEmployeeId = null; // Track current employee

	// Initialize with empty data
	let attendanceData = {};

	let employeeData = {};
	let allEmployees = [];

	function fetchAndRenderEmployees() {
		fetchEmployees().then(employees => {
			renderEmployeeDropdown(employees.result.employees);
			const defaultEmployee = employees.result.employees.find(e => e.is_current_user);
			if (defaultEmployee) {
				selectEmployee(employees.result.employees, defaultEmployee.id);
			}
		}).catch(error => {
			console.error('Error loading employees:', error);
		});
	}

	fetchAndRenderEmployees();


	const employeeSelector = document.getElementById('employeeSelector');
	const employeeDropdown = document.getElementById('employeeDropdown');

	if (employeeSelector && employeeDropdown) {
		employeeSelector.addEventListener('click', function(e) {
			e.stopPropagation();
			employeeDropdown.style.display = employeeDropdown.style.display === 'block' ? 'none' : 'block';
		});

		document.addEventListener('click', function() {
			employeeDropdown.style.display = 'none';
		});
	}

	function fetchEmployees() {
		return $.ajax({
			url: '/attendance/get_attendance_employees',
			type: 'POST',
			contentType: 'application/json',
			dataType: 'json',
			data: JSON.stringify({}),
			success: function(response) {
				if (response.result && response.result.success) {
					allEmployees = response.result.employees;
					return allEmployees;
				} else {
					console.error('Error fetching employees:', response);
					document.getElementById('calendarDays').innerHTML = `<div class="loading" style="width:250px;">${response.result.error}...</div>`;
					throw new Error("Failed to fetch employees");
				}
			},
			error: function(xhr, status, error) {
				console.error('AJAX error:', error);
				throw new Error("Failed to fetch employees");
			}
		});
	}


	// Render employee dropdown
	function renderEmployeeDropdown(allEmployees) {
		const dropdown = document.getElementById('employeeDropdown');
		dropdown.innerHTML = '';
		const employeesArray = Array.isArray(allEmployees) ? allEmployees : [];
		employeesArray.forEach(employee => {
			const employeeElement = document.createElement('div');
			employeeElement.className = 'employee-option';
			employeeElement.innerHTML = `
				<div class="employee-option-name">${employee.name}</div>
				${employee.is_current_user ? '<div class="employee-option-you">(You)</div>' : ''}
			`;
			employeeElement.addEventListener('click', () => selectEmployee(allEmployees, employee.id));
			dropdown.appendChild(employeeElement);
		});
	}

	// Select employee handler
	function selectEmployee(allemployees, employeeId) {
		currentEmployeeId = employeeId;
		const employee = allemployees.find(e => e.id === employeeId);
		if (employee) {
			document.getElementById('currentEmployee').textContent = employee.name;
			document.getElementById('employeeDropdown').style.display = 'none';
			fetchAttendanceData(currentDate.getFullYear(), currentDate.getMonth() + 1);
		}
	}


	// Initialize
	fetchAttendanceData(currentDate.getFullYear(), currentDate.getMonth() + 1);

	// Event listeners
	const monthSelector = document.getElementById('monthSelector');
	if (monthSelector) {
		monthSelector.addEventListener('click', function() {
			modalCustomYear = currentDate.getFullYear();
			const modalCustomYearEl = document.getElementById('modalCustomYear');
			if (modalCustomYearEl) modalCustomYearEl.textContent = modalCustomYear;
			const monthYearModalCustom = document.getElementById('monthYearModalCustom');
			if (monthYearModalCustom) monthYearModalCustom.style.display = 'flex';
			renderMonthOptions(modalCustomYear);
		});
	}

	const closeMonthModalCustom = document.getElementById('closeMonthModalCustom');
	if (closeMonthModalCustom) {
		closeMonthModalCustom.addEventListener('click', function() {
			const monthYearModalCustom = document.getElementById('monthYearModalCustom');
			if (monthYearModalCustom) monthYearModalCustom.style.display = 'none';
		});
	}

	document.addEventListener('click', function(e) {
		const monthYearModalCustom = document.getElementById('monthYearModalCustom');
		if (monthYearModalCustom && e.target === monthYearModalCustom) {
			monthYearModalCustom.style.display = 'none';
		}
	});

	const prevMonth = document.getElementById('prevMonth');
	if (prevMonth) {
		prevMonth.addEventListener('click', function() {
			animateCalendarTransition('left');
			setTimeout(() => {
				currentDate.setMonth(currentDate.getMonth() - 1);
				fetchAttendanceData(currentDate.getFullYear(), currentDate.getMonth() + 1);
			}, 200);
		});
	}

	const nextMonth = document.getElementById('nextMonth');
	if (nextMonth) {
		nextMonth.addEventListener('click', function() {
			animateCalendarTransition('right');
			setTimeout(() => {
				currentDate.setMonth(currentDate.getMonth() + 1);
				fetchAttendanceData(currentDate.getFullYear(), currentDate.getMonth() + 1);
			}, 200);
		});
	}

	const prevYear = document.getElementById('prevYear');
	if (prevYear) {
		prevYear.addEventListener('click', function() {
			modalCustomYear--;
			const modalCustomYearEl = document.getElementById('modalCustomYear');
			if (modalCustomYearEl) modalCustomYearEl.textContent = modalCustomYear;
			renderMonthOptions(modalCustomYear);
		});
	}

	const nextYear = document.getElementById('nextYear');
	if (nextYear) {
		nextYear.addEventListener('click', function() {
			modalCustomYear++;
			const modalCustomYearEl = document.getElementById('modalCustomYear');
			if (modalCustomYearEl) modalCustomYearEl.textContent = modalCustomYear;
			renderMonthOptions(modalCustomYear);
		});
	}

	// Fetch attendance data from Odoo
	function fetchAttendanceData(year, month) {
		// Show loading state
		document.getElementById('calendarDays').innerHTML = '<div class="loading">Loading...</div>';

		// Make AJAX call to your Odoo controller
		$.ajax({
			url: '/attendance/get_month_data',
			type: 'POST',
			data: JSON.stringify({
				year: year,
				month: month,
				employee_id: currentEmployeeId
			}),
			contentType: 'application/json',
			dataType: 'json',
			success: function(response) {
				if (response.result.success) {
					attendanceData = response.result.data;
					renderCalendar(currentDate);
					updateAttendanceCard(selectedDate);
					updateEmployeeInfo(response.result.data.employee);
				} else {
					document.getElementById('calendarDays').innerHTML = `<div class="loading" style="width:250px;">${response.result.error}...</div>`;
					console.error('Error fetching attendance data:', response);
					console.error('Error fetching attendance data:', response.result.error);
				}
			},
			error: function(xhr, status, error) {
				console.error('AJAX error:', error);
			}
		});
	}

	// Animation for calendar transition
	function animateCalendarTransition(direction) {
		const calendar = document.getElementById('calendarDays');
		calendar.style.animation = 'none';
		calendar.style.opacity = '0';
		calendar.style.transform = direction === 'left' ? 'translateX(30px)' : 'translateX(-30px)';

		setTimeout(() => {
			calendar.style.transition = 'all 0.3s ease-out';
			calendar.style.opacity = '1';
			calendar.style.transform = 'translateX(0)';
		}, 10);
	}

	

	// Update employee info section
	function updateEmployeeInfo(employee) {
		const name = employee.name || 'No Name';
		const jobPosition = employee.job_position || 'N/A';

		document.querySelector('.employee-info h3').textContent = name;
		document.querySelector('.employee-info p').textContent = jobPosition;

		// Handle employee image
		const avatarElement = document.querySelector('.employee-avatar');
		if (employee.image) {
			avatarElement.innerHTML = `<img src="${employee.image}" alt="${name}" />`;
		} else {
			// Use initials if no image
			const initials = name.split(' ').map(n => n[0]).join('').toUpperCase();
			avatarElement.textContent = initials;
			avatarElement.style.backgroundColor = getRandomColor();
			avatarElement.style.display = 'flex';
			avatarElement.style.alignItems = 'center';
			avatarElement.style.justifyContent = 'center';
		}
	}

	// Helper function for random color
	function getRandomColor() {
		const colors = ['#4361ee', '#3a0ca3', '#7209b7', '#f72585', '#480ca8'];
		return colors[Math.floor(Math.random() * colors.length)];
	}

	// Render calendar with staggered animations
	function renderCalendar(date) {
		document.getElementById('currentMonthYear').textContent =
			date.toLocaleDateString('en-US', { month: 'long', year: 'numeric' });

		const firstDay = new Date(date.getFullYear(), date.getMonth(), 1);
		const lastDay = new Date(date.getFullYear(), date.getMonth() + 1, 0);
		const daysInMonth = lastDay.getDate();
		const startingDay = firstDay.getDay();
		const monthNames = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
			"Jul", "Aug", "Sep", "Oct", "Nov", "Dec"
		];
		const currentMonthShort = monthNames[date.getMonth()];
		const todayDateString = today.toDateString();

		let calendarHTML = '';

		// Empty cells for days before first day
		for (let i = 0; i < startingDay; i++) {
			calendarHTML += '<div class="calendar-day"></div>';
		}

		// Days of month with staggered animations
		for (let day = 1; day <= daysInMonth; day++) {
			const dayDate = new Date(date.getFullYear(), date.getMonth(), day);
			const dateKey = `${dayDate.getFullYear()}-${dayDate.getMonth()+1}-${dayDate.getDate()}`;
			const isToday = dayDate.toDateString() === todayDateString;
			const isSelected = dayDate.toDateString() === selectedDate.toDateString();
			const data = attendanceData[dateKey] || {};
			const isFuture = dayDate > today;

			let status = data.status || '';
			let statusClass = '';
			let displayText = '';
			let badgesHTML = '';
			let day_status = '';

			// Determine status and display text
			if (status === 'present') {
				statusClass = 'status-present';
				displayText = 'PRESENT';
				day_status = 'ON DUTY'

				// Add custom small badges
				if (data.late_arrival) {
					badgesHTML += '<span style="font-size:9px !important;" class="status-badge status-late"><i class="fa fa-clock-o"></i> LATE</span>';
				}
				if (data.early_left) {
					badgesHTML += '<span style="font-size:9px !important;" class="status-badge status-early"><i class="fa fa-forward"></i> EARLY</span>';
				}
				// if (data.over_time) {
				//     badgesHTML += '<span style="font-size:9px !important;" class="status-badge status-overtime"><i class="fa fa-plus-circle"></i> OVERTIME</span>';
				// }
			} else if (status === 'absent' && !isFuture) {
				statusClass = 'status-absent';
				displayText = 'ABSENT';
				day_status = 'ON DUTY'

			} else if (status === 'leave') {
				statusClass = 'status-off';
				displayText = data.leave_type || data.display_status || 'LEAVE';
			} else if (status === 'off') {
				statusClass = 'status-off';
				displayText = data.display_status || 'OFF DUTY';
			} else if (isFuture) {
				status = 'future';
				displayText = '';
			} else {
				status = 'no-record';
				displayText = 'NO RECORD';
			}

			if (day_status != '') {
				calendarHTML += `
				<div class="calendar-day ${isToday ? 'day-today' : ''} ${isSelected ? 'selected' : ''} ${status === 'absent' ? 'day-absent' : ''}" 
					 onclick="selectDate(${dayDate.getFullYear()}, ${dayDate.getMonth()}, ${dayDate.getDate()})"
					 style="animation-delay: ${day * 0.03}s">
					<div class="day-info">
						<div class="day-number ${status === 'absent' ? 'absent-day-number' : ''}">${day}</div>
						<div class="day-month">${currentMonthShort}</div>
						<div class="day-status" style="color: green !important; font-weight: bold !important; font-size: 10px !important;">${day_status}</div>
					</div>
					${displayText ? `<div class="day-status ${statusClass}">${displayText}</div>` : ''}
					${badgesHTML ? `<div class="day-mini-badges">${badgesHTML}</div>` : ''}
				</div>
			`;
			} else {
				calendarHTML += `
				<div class="calendar-day ${isToday ? 'day-today' : ''} ${isSelected ? 'selected' : ''} ${status === 'absent' ? 'day-absent' : ''}" 
					 onclick="selectDate(${dayDate.getFullYear()}, ${dayDate.getMonth()}, ${dayDate.getDate()})"
					 style="animation-delay: ${day * 0.03}s">
					<div class="day-info">
						<div class="day-number ${status === 'absent' ? 'absent-day-number' : ''}">${day}</div>
						<div class="day-month">${currentMonthShort}</div>
					</div>
					${displayText ? `<div class="day-status ${statusClass}">${displayText}</div>` : ''}
					${badgesHTML ? `<div class="day-mini-badges">${badgesHTML}</div>` : ''}
				</div>
			`;
			}
		}

		document.getElementById('calendarDays').innerHTML = calendarHTML;
	}

	// Update attendance card with animation
	function updateAttendanceCard(date) {
		const dateKey = `${date.getFullYear()}-${date.getMonth()+1}-${date.getDate()}`;
		const data = attendanceData[dateKey] || {};
		const isFuture = date > today;

		let status = 'NO RECORD';
		let statusClass = 'status-present';
		let timings = 'No attendance data';
		let shift = 'No shift data';
		let badgesHTML = '';
		let todays_attendance = 'N/A';

		if (data.status === 'present') {
			status = 'PRESENT';
			statusClass = 'status-present';
			timings = data.timings || 'No check-in/check-out recorded';
			shift = data.shift || 'N/A';

			// Add badges
			if (data.late_arrival) {
				badgesHTML += '<span class="status-badge status-late"><i class="fa fa-clock-o"></i> LATE</span>';
			}
			if (data.early_left) {
				badgesHTML += '<span class="status-badge status-early"><i class="fa fa-forward"></i> EARLY</span>';
			}
			// if (data.over_time) {
			//     badgesHTML += '<span class="status-badge status-overtime"><i class="fa fa-plus-circle"></i> OVERTIME</span>';
			// }
		} else if (data.status === 'absent' && !isFuture) {
			status = 'ABSENT';
			statusClass = 'status-absent';
			timings = data.timings || 'No check-in/check-out recorded';
			shift = data.shift || 'N/A';
		} else if (data.status === 'leave') {
			status = data.leave_type || data.display_status || 'LEAVE';
			statusClass = 'status-off';
			timings = data.timings || 'No check-in/check-out recorded';
			shift = data.shift || 'N/A';
		} else if (data.status === 'off') {
			status = data.display_status || 'OFF DUTY';
			statusClass = 'status-off';
			timings = data.timings || 'No check-in/check-out recorded';
			shift = data.shift || 'N/A';
		}

		// Update badge
		const badge = document.getElementById('attendanceBadge');
		badge.className = `status-badge ${statusClass}`;
		badge.innerHTML = `<i class="fa fa-${status === 'PRESENT' ? 'user-check' : status === 'ABSENT' ? 'user-times' : 'moon'}"></i><span>${status}</span>`;

		// Update details
		document.getElementById('attendanceStatus').textContent = status;
		document.getElementById('shiftValue').textContent = shift;
		document.getElementById('attendanceTimings').textContent = timings;
		const breaksEl = document.getElementById('attendanceBreaks');
		const missingPunchEl = document.getElementById('missingPunchBreaks');
		const breaksRow = document.getElementById('breaksRow');

		if (breaksEl && breaksRow) {
		    const breaks = data.breaks || '';
		    breaksEl.textContent = breaks;
		    if (missingPunchEl) missingPunchEl.textContent = '';
		    breaksRow.style.display = breaks ? '' : 'none';
		}
		document.getElementById('attendanceDate').textContent =
			date.toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' });
		todays_attendance = date.toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' });

		if (data.status) {
			document.getElementById('todays-attendance').textContent = `${todays_attendance} | Attendance`
		} else {
			document.getElementById('todays-attendance').textContent = `N/A | Attendance`
			document.getElementById('attendanceDate').textContent = `N/A | Attendance`
		}

		// Update badges container
		const badgesContainer = document.getElementById('attendanceBadges');
		if (badgesContainer) {
			badgesContainer.innerHTML = badgesHTML;
		}
	}

	// Render month options
	function renderMonthOptions(year) {
		const months = [
			'January', 'February', 'March', 'April',
			'May', 'June', 'July', 'August',
			'September', 'October', 'November', 'December'
		];

		let optionsHTML = '';
		months.forEach((month, index) => {
			const isSelected = year === currentDate.getFullYear() &&
				index === currentDate.getMonth();
			optionsHTML += `
					<div class="month-option ${isSelected ? 'selected' : ''}" 
						 onclick="selectMonth(${index}, ${year})"
						 style="animation-delay: ${index * 0.05}s">
						${month}
					</div>
				`;
		});

		document.getElementById('monthGrid').innerHTML = optionsHTML;

		// Add animation to month options
		const options = document.querySelectorAll('.month-option');
		options.forEach(option => {
			option.style.animation = 'popIn 0.4s ease-out';
			option.style.animationFillMode = 'both';
		});
	}

	// Global functions for HTML event handlers
	window.selectMonth = function(monthIndex, year) {
		currentDate = new Date(year, monthIndex, 1);
		animateCalendarTransition('fade');
		setTimeout(() => {
			fetchAttendanceData(year, monthIndex + 1);
		}, 200);
		document.getElementById('monthYearModalCustom').style.display = 'none';
	};

	window.selectDate = function(year, month, day) {
		selectedDate = new Date(year, month, day);
		updateAttendanceCard(selectedDate);

		// Highlight selected date
		const days = document.querySelectorAll('.calendar-day');
		days.forEach(dayEl => {
			dayEl.classList.remove('selected');
		});

		const selectedDay = document.querySelector(`.calendar-day[onclick="selectDate(${year}, ${month}, ${day})"]`);
		if (selectedDay) {
			selectedDay.classList.add('selected');
			selectedDay.style.animation = 'pulse 0.5s ease-out';
		}
	};
});