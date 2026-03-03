# Performance Management System

## Done so far:

### Access Rigts:

Created four users:
- HR
- Reveiwer
- Supervisor
- Employee

Must assign HR manually

If you are assigned as a manager/secondary manager for an employee then the user is granted access rights of Supervisor  
#Note: Supervisor and Secondary Supervisor has the same access rights

If you are assigned as a reviewer for an employee, you are granted the access rights for Reviewer

If you have been assigned a reviewer or a manager/secondary manager then you are granted the access rights of an Employee


### Template Creation:

HR can create templates for different Employees using Evaluation Group

Depending on evaluation group, employees can see their own plan.

A template consists of the following:
- KRA - Key Resource Indicator
- KPI - Key Performance Indicator

A template can have N number of KRAs and KRAs can have N number of KPIs

HR can add KRAs for a template

For each of the KRAs the HR can add multiple KPIs.

KPI contains the following fields:
- KPI name
- Description
- Score
- Criteria


### Cycle Activation

HR can activate PMS cycle

Can choose cycle type (Annually/Half-yearly/Probation)

Select employees that will participate in the cycle (All / manually select)

For an employee participate in a cycle the following must be met:
- Must have a supervisor
- Must have an evaluation group assigned
- Must have a template created for specific evaluatioin group


After HR activates cycle, employee can see their own planning form

Employee fills up planning form and submits to supervisor

Supervisor can either reject or approve

If rejected, employee needs to fill form again

If approved it moves on to secondary supervisor

Secondary supervisor can approve or reject

If rejected employee starts planning all over again

If approved it moves on to final reviewer

If reviewer rejects employee starts all over again 

If approved, planning is done for the said employee


### Conditionals:

Its mandatory that an employee have a supervisor to participate in a PMS Cycle

Secondary Supervisor and Reviewer are kept optional for now


Flow of approval:

Employee submits plan

Manager (approves/rejects) -> secondary manager (approves/rejects) -> reviewer(approves/rejects) -> complete

If emp doesnt have secondary manager then:
Manager (approves/rejects) -> reviewer(approves/rejects) -> complete

If emp doesnt have reviewer then:
Manager (approves/rejects) -> secondary manager (approves/rejects) -> complete

If emp doesnt have secondary manager and reviwer:
Manager (approves/rejects) -> complete

And the flow must of approval must always be
Manager -> Secondary Manager -> Reviewer
