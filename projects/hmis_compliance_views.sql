/*
===========================================================================
  HMIS Compliance Reporting Views
  ================================
  SQL Server views for HMIS reporting against a relational case management
  database. Covers active enrollments, data completeness, demographics,
  length of stay, and housing outcomes.
  
  Author: James Calby
  Platform: SQL Server 2016+
  
  NOTE: These views use a generic HMIS schema for demonstration purposes.
  Table and column names should be mapped to your specific HMIS platform
  (CaseWorthy, ClientTrack, etc.) before deployment.
===========================================================================
*/


-- ---------------------------------------------------------------------------
-- VIEW 1: Active Enrollments by Program
-- Shows current enrollment counts grouped by program and project type.
-- Useful for operational dashboards and capacity monitoring.
-- ---------------------------------------------------------------------------

CREATE OR ALTER VIEW vw_ActiveEnrollmentsByProgram
AS
SELECT
    p.ProgramName,
    p.ProjectType,
    p.FundingSource,
    COUNT(DISTINCT e.ClientID)          AS ActiveClients,
    COUNT(DISTINCT e.HouseholdID)       AS ActiveHouseholds,
    MIN(e.EntryDate)                    AS EarliestEntry,
    MAX(e.EntryDate)                    AS MostRecentEntry
FROM
    Enrollment e
    INNER JOIN Program p ON e.ProgramID = p.ProgramID
WHERE
    e.ExitDate IS NULL
    AND e.EntryDate <= GETDATE()
GROUP BY
    p.ProgramName,
    p.ProjectType,
    p.FundingSource;
GO


-- ---------------------------------------------------------------------------
-- VIEW 2: Data Completeness Scorecard
-- Calculates the percentage of non-null values for each HUD Universal
-- Data Element across all active enrollments. Designed to be run weekly
-- for ongoing data quality monitoring.
-- ---------------------------------------------------------------------------

CREATE OR ALTER VIEW vw_DataCompletenessScorecard
AS
WITH ActiveRecords AS (
    SELECT
        c.ClientID,
        c.FirstName,
        c.LastName,
        c.DOB,
        c.SSN,
        c.Gender,
        c.Race,
        c.Ethnicity,
        c.VeteranStatus,
        e.EnrollmentID,
        e.EntryDate,
        e.ProgramID,
        ea.PriorLivingSituation,
        ea.DisablingCondition,
        ea.MonthlyIncome,
        ea.IncomeFromAnySource,
        ea.InsuranceFromAnySource,
        ea.DomesticViolenceSurvivor,
        e.RelationshipToHoH
    FROM
        Client c
        INNER JOIN Enrollment e ON c.ClientID = e.ClientID
        LEFT JOIN EntryAssessment ea ON e.EnrollmentID = ea.EnrollmentID
    WHERE
        e.ExitDate IS NULL
),
TotalCount AS (
    SELECT COUNT(*) AS Total FROM ActiveRecords
)
SELECT
    'FirstName'                AS FieldName,
    ROUND(SUM(CASE WHEN ar.FirstName IS NOT NULL AND ar.FirstName != '' THEN 1.0 ELSE 0 END) / tc.Total * 100, 1) AS CompletePct,
    tc.Total                   AS TotalRecords,
    SUM(CASE WHEN ar.FirstName IS NULL OR ar.FirstName = '' THEN 1 ELSE 0 END) AS MissingCount
FROM ActiveRecords ar CROSS JOIN TotalCount tc
GROUP BY tc.Total

UNION ALL

SELECT
    'DOB',
    ROUND(SUM(CASE WHEN ar.DOB IS NOT NULL THEN 1.0 ELSE 0 END) / tc.Total * 100, 1),
    tc.Total,
    SUM(CASE WHEN ar.DOB IS NULL THEN 1 ELSE 0 END)
FROM ActiveRecords ar CROSS JOIN TotalCount tc
GROUP BY tc.Total

UNION ALL

SELECT
    'SSN',
    ROUND(SUM(CASE WHEN ar.SSN IS NOT NULL AND ar.SSN != '' THEN 1.0 ELSE 0 END) / tc.Total * 100, 1),
    tc.Total,
    SUM(CASE WHEN ar.SSN IS NULL OR ar.SSN = '' THEN 1 ELSE 0 END)
FROM ActiveRecords ar CROSS JOIN TotalCount tc
GROUP BY tc.Total

UNION ALL

SELECT
    'Gender',
    ROUND(SUM(CASE WHEN ar.Gender IS NOT NULL THEN 1.0 ELSE 0 END) / tc.Total * 100, 1),
    tc.Total,
    SUM(CASE WHEN ar.Gender IS NULL THEN 1 ELSE 0 END)
FROM ActiveRecords ar CROSS JOIN TotalCount tc
GROUP BY tc.Total

UNION ALL

SELECT
    'VeteranStatus',
    ROUND(SUM(CASE WHEN ar.VeteranStatus IS NOT NULL THEN 1.0 ELSE 0 END) / tc.Total * 100, 1),
    tc.Total,
    SUM(CASE WHEN ar.VeteranStatus IS NULL THEN 1 ELSE 0 END)
FROM ActiveRecords ar CROSS JOIN TotalCount tc
GROUP BY tc.Total

UNION ALL

SELECT
    'PriorLivingSituation',
    ROUND(SUM(CASE WHEN ar.PriorLivingSituation IS NOT NULL THEN 1.0 ELSE 0 END) / tc.Total * 100, 1),
    tc.Total,
    SUM(CASE WHEN ar.PriorLivingSituation IS NULL THEN 1 ELSE 0 END)
FROM ActiveRecords ar CROSS JOIN TotalCount tc
GROUP BY tc.Total

UNION ALL

SELECT
    'DisablingCondition',
    ROUND(SUM(CASE WHEN ar.DisablingCondition IS NOT NULL THEN 1.0 ELSE 0 END) / tc.Total * 100, 1),
    tc.Total,
    SUM(CASE WHEN ar.DisablingCondition IS NULL THEN 1 ELSE 0 END)
FROM ActiveRecords ar CROSS JOIN TotalCount tc
GROUP BY tc.Total

UNION ALL

SELECT
    'MonthlyIncome',
    ROUND(SUM(CASE WHEN ar.MonthlyIncome IS NOT NULL THEN 1.0 ELSE 0 END) / tc.Total * 100, 1),
    tc.Total,
    SUM(CASE WHEN ar.MonthlyIncome IS NULL THEN 1 ELSE 0 END)
FROM ActiveRecords ar CROSS JOIN TotalCount tc
GROUP BY tc.Total;
GO


-- ---------------------------------------------------------------------------
-- VIEW 3: Demographics Summary
-- Aggregated demographic breakdown of currently enrolled clients.
-- Supports PIT count preparation and program equity analysis.
-- ---------------------------------------------------------------------------

CREATE OR ALTER VIEW vw_DemographicsSummary
AS
SELECT
    p.ProgramName,
    
    -- Gender breakdown
    SUM(CASE WHEN c.Gender = 0 THEN 1 ELSE 0 END)     AS Female,
    SUM(CASE WHEN c.Gender = 1 THEN 1 ELSE 0 END)     AS Male,
    SUM(CASE WHEN c.Gender = 2 THEN 1 ELSE 0 END)     AS TransMale,
    SUM(CASE WHEN c.Gender = 3 THEN 1 ELSE 0 END)     AS TransFemale,
    SUM(CASE WHEN c.Gender = 4 THEN 1 ELSE 0 END)     AS NonBinary,
    SUM(CASE WHEN c.Gender IN (8, 9, 99) THEN 1 ELSE 0 END) AS GenderNotCollected,
    
    -- Veteran status
    SUM(CASE WHEN c.VeteranStatus = 1 THEN 1 ELSE 0 END) AS Veterans,
    SUM(CASE WHEN c.VeteranStatus = 0 THEN 1 ELSE 0 END) AS NonVeterans,
    
    -- Age groups (calculated from DOB)
    SUM(CASE WHEN DATEDIFF(YEAR, c.DOB, GETDATE()) < 18 THEN 1 ELSE 0 END)           AS Under18,
    SUM(CASE WHEN DATEDIFF(YEAR, c.DOB, GETDATE()) BETWEEN 18 AND 24 THEN 1 ELSE 0 END)  AS Age18to24,
    SUM(CASE WHEN DATEDIFF(YEAR, c.DOB, GETDATE()) BETWEEN 25 AND 54 THEN 1 ELSE 0 END)  AS Age25to54,
    SUM(CASE WHEN DATEDIFF(YEAR, c.DOB, GETDATE()) >= 55 THEN 1 ELSE 0 END)           AS Age55Plus,
    
    -- Chronic homelessness indicator
    SUM(CASE 
        WHEN ea.DisablingCondition = 1 
        AND ea.PriorLivingSituation IN (1, 16, 18)  -- Place not meant for habitation, ES, SH
        AND ea.LengthOfStay >= 365
        THEN 1 ELSE 0 
    END) AS ChronicallyHomeless,
    
    COUNT(DISTINCT e.ClientID) AS TotalClients
FROM
    Client c
    INNER JOIN Enrollment e ON c.ClientID = e.ClientID
    INNER JOIN Program p ON e.ProgramID = p.ProgramID
    LEFT JOIN EntryAssessment ea ON e.EnrollmentID = ea.EnrollmentID
WHERE
    e.ExitDate IS NULL
GROUP BY
    p.ProgramName;
GO


-- ---------------------------------------------------------------------------
-- VIEW 4: Length of Stay Analysis
-- Calculates average and median length of stay for exited clients,
-- grouped by program and exit destination category.
-- ---------------------------------------------------------------------------

CREATE OR ALTER VIEW vw_LengthOfStayAnalysis
AS
WITH ExitedClients AS (
    SELECT
        e.EnrollmentID,
        e.ClientID,
        p.ProgramName,
        p.ProjectType,
        e.EntryDate,
        e.ExitDate,
        ex.Destination,
        DATEDIFF(DAY, e.EntryDate, e.ExitDate) AS LengthOfStayDays,
        CASE
            WHEN ex.Destination IN (3, 10, 11, 19, 20, 21, 22, 23, 26, 28, 31, 33, 34)
                THEN 'Permanent Housing'
            WHEN ex.Destination IN (1, 2, 12, 13, 14, 15, 16, 18, 25, 27, 29, 32)
                THEN 'Temporary / Institutional'
            WHEN ex.Destination IN (8, 9, 17, 24, 30, 37, 99)
                THEN 'Other / Unknown'
            ELSE 'Not Recorded'
        END AS DestinationCategory
    FROM
        Enrollment e
        INNER JOIN Program p ON e.ProgramID = p.ProgramID
        LEFT JOIN ExitAssessment ex ON e.EnrollmentID = ex.EnrollmentID
    WHERE
        e.ExitDate IS NOT NULL
        AND e.EntryDate IS NOT NULL
        AND e.ExitDate >= e.EntryDate
)
SELECT
    ProgramName,
    DestinationCategory,
    COUNT(*)                                AS ExitCount,
    AVG(LengthOfStayDays)                  AS AvgLOS_Days,
    MIN(LengthOfStayDays)                  AS MinLOS_Days,
    MAX(LengthOfStayDays)                  AS MaxLOS_Days,
    ROUND(AVG(LengthOfStayDays) / 30.0, 1) AS AvgLOS_Months
FROM
    ExitedClients
GROUP BY
    ProgramName,
    DestinationCategory;
GO


-- ---------------------------------------------------------------------------
-- VIEW 5: Housing Outcomes Tracker
-- Tracks permanent housing placement rates by program for the current
-- fiscal year. Key metric for APR reporting and program performance.
-- ---------------------------------------------------------------------------

CREATE OR ALTER VIEW vw_HousingOutcomes
AS
WITH FiscalYearExits AS (
    SELECT
        e.EnrollmentID,
        e.ClientID,
        p.ProgramName,
        p.ProjectType,
        p.FundingSource,
        e.ExitDate,
        ex.Destination,
        CASE
            WHEN ex.Destination IN (3, 10, 11, 19, 20, 21, 22, 23, 26, 28, 31, 33, 34)
                THEN 1
            ELSE 0
        END AS PermanentHousingExit
    FROM
        Enrollment e
        INNER JOIN Program p ON e.ProgramID = p.ProgramID
        LEFT JOIN ExitAssessment ex ON e.EnrollmentID = ex.EnrollmentID
    WHERE
        e.ExitDate IS NOT NULL
        -- Current HUD fiscal year: Oct 1 - Sep 30
        AND e.ExitDate >= DATEFROMPARTS(
            CASE WHEN MONTH(GETDATE()) >= 10 THEN YEAR(GETDATE()) ELSE YEAR(GETDATE()) - 1 END,
            10, 1
        )
        AND e.ExitDate < DATEFROMPARTS(
            CASE WHEN MONTH(GETDATE()) >= 10 THEN YEAR(GETDATE()) + 1 ELSE YEAR(GETDATE()) END,
            10, 1
        )
)
SELECT
    ProgramName,
    FundingSource,
    COUNT(*)                                                    AS TotalExits,
    SUM(PermanentHousingExit)                                   AS PermanentHousingExits,
    ROUND(
        CAST(SUM(PermanentHousingExit) AS FLOAT) / 
        NULLIF(COUNT(*), 0) * 100, 
        1
    )                                                           AS PH_PlacementRate,
    SUM(CASE WHEN Destination IS NULL THEN 1 ELSE 0 END)       AS MissingDestination,
    ROUND(
        CAST(SUM(CASE WHEN Destination IS NULL THEN 1 ELSE 0 END) AS FLOAT) / 
        NULLIF(COUNT(*), 0) * 100, 
        1
    )                                                           AS MissingDestinationPct
FROM
    FiscalYearExits
GROUP BY
    ProgramName,
    FundingSource;
GO


-- ---------------------------------------------------------------------------
-- VIEW 6: Weekly Error Trend
-- Shows data quality error counts by week for trending analysis.
-- Requires a DataQualityLog table populated by automated validation jobs.
-- ---------------------------------------------------------------------------

CREATE OR ALTER VIEW vw_WeeklyErrorTrend
AS
SELECT
    DATEPART(YEAR, RunDate)                     AS RunYear,
    DATEPART(WEEK, RunDate)                     AS RunWeek,
    MIN(RunDate)                                AS WeekStarting,
    FieldName,
    ErrorType,
    SUM(ErrorCount)                             AS TotalErrors,
    AVG(ErrorCount)                             AS AvgErrorsPerRun,
    COUNT(*)                                    AS RunsInWeek
FROM
    DataQualityLog
WHERE
    RunDate >= DATEADD(MONTH, -6, GETDATE())
GROUP BY
    DATEPART(YEAR, RunDate),
    DATEPART(WEEK, RunDate),
    FieldName,
    ErrorType;
GO
