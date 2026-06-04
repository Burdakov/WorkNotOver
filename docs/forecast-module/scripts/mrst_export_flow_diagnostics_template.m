% MRST Flow Diagnostics export template for waterflood_proxy_hm
% This file is a template. It is not expected to run in Python tests.
%
% Expected CSV output columns:
% injector_id,producer_id,allocation_factor,time_of_flight_days,swept_volume,drainage_volume
%
% User must adapt deck path, well names, units, and output path.

mrstModule add ad-core ad-props deckformat diagnostics

 deck_path = 'data/model.DATA';
 out_csv = 'data/mrst_exports/flow_diagnostics.csv';

 deck = readEclipseDeck(deck_path);
 deck = convertDeckUnits(deck);
 G = initEclipseGrid(deck);
 G = computeGeometry(G);
 rock = initEclipseRock(deck);
 fluid = initDeckADIFluid(deck);

% Build model from deck. Adapt phases and options as needed.
 model = selectModelFromDeck(G, rock, fluid, deck);

% Initialize state and wells. Real projects should use restart or schedule state.
 state0 = initResSol(G, deck.SOLUTION.PRESSURE(1));
 schedule = convertDeckScheduleToMRST(model, deck);
 W = schedule.control(1).W;

% Solve a representative pressure problem and run diagnostics.
% This is deliberately schematic; adapt to your MRST version and model.
 state = incompTPFA(state0, G, rock, 'wells', W);
 D = computeTOFandTracer(state, G, rock, 'wells', W);

% TODO: Convert MRST diagnostics to injector-producer allocation matrix.
% The actual extraction depends on MRST diagnostics objects and well naming.
% Export a table with the expected columns.

T = table();
% T.injector_id = ...;
% T.producer_id = ...;
% T.allocation_factor = ...;
% T.time_of_flight_days = ...;
% T.swept_volume = ...;
% T.drainage_volume = ...;

writetable(T, out_csv);
