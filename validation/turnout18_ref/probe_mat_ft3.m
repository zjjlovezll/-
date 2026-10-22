% Lean probe: only ModeFreq and N_Node (loading ModeShape pulls ~750 MB of modal matrices).
root = 'G:\研究生\SDITT-RW-FT-250728\SDITT-RW-FT-250728';
file = fullfile(root, 'Mat_FT_S8b.mat');

data = load(file, 'ModeFreq');
freq = data.ModeFreq.FT_All;
f = freq(:, 1);
fprintf('FT_All: %d modes x %d columns\n', size(freq, 1), size(freq, 2));
fprintf('frequency  min %.3f  max %.3f Hz\n', min(f), max(f));
fprintf('first five %s\n', mat2str(f(1:5)', 6));
fprintf('modes below 200 Hz: %d\n', sum(f < 200));
fprintf('modes 100-1000 Hz : %d\n', sum(f >= 100 & f <= 1000));
if size(freq, 2) > 1
    zeta = freq(:, 2);
    fprintf('column 2: min %.3e max %.3e (damping ratio?)\n', min(zeta), max(zeta));
end

data2 = load(file, 'N_Node');
names = fieldnames(data2.N_Node);
total = 0;
for k = 1:numel(names)
    value = data2.N_Node.(names{k});
    if isnumeric(value)
        total = total + value;
        fprintf('  N_Node.%-20s %d nodes\n', names{k}, value);
    else
        fprintf('  N_Node.%-20s (%s)\n', names{k}, class(value));
    end
end
fprintf('total nodes = %d\n', total);
fprintf('done\n');
