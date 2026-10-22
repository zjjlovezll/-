% Deeper look: how many modes/nodes SDITT's flexible track carries, and what its frequencies are.
root = 'G:\研究生\SDITT-RW-FT-250728\SDITT-RW-FT-250728';
file = fullfile(root, 'Mat_FT_S8b.mat');

fprintf('=== struct fields ===\n');
for name = {'DOF_Node','ModeFreq','ModeShape','ModeShape_Mapping','N_Node','Pos_Node'}
    data = load(file, name{1});
    value = data.(name{1});
    fields = fieldnames(value);
    fprintf('%-20s  fields: %s\n', name{1}, strjoin(fields', ', '));
    for k = 1:numel(fields)
        item = value.(fields{k});
        if isnumeric(item)
            fprintf('    .%-14s %-10s %s\n', fields{k}, class(item), mat2str(size(item)));
        elseif iscell(item)
            fprintf('    .%-14s cell %s\n', fields{k}, mat2str(size(item)));
        elseif isstruct(item)
            fprintf('    .%-14s struct %s\n', fields{k}, mat2str(size(item)));
        end
    end
    clear data value
end

fprintf('\n=== frequency content ===\n');
data = load(file, 'ModeFreq');
fields = fieldnames(data.ModeFreq);
for k = 1:numel(fields)
    item = data.ModeFreq.(fields{k});
    if isnumeric(item) && numel(item) > 1
        values = sort(item(:));
        fprintf('.%s: %d values, min %.2f Hz, max %.2f Hz, first five %s\n', ...
                fields{k}, numel(values), values(1), values(end), ...
                mat2str(values(1:min(5, numel(values)))', 6));
    end
end

fprintf('\n=== mode shape block ===\n');
data2 = load(file, 'ModeShape');
fields2 = fieldnames(data2.ModeShape);
for k = 1:numel(fields2)
    item = data2.ModeShape.(fields2{k});
    fprintf('.%s: %s %s\n', fields2{k}, class(item), mat2str(size(item)));
end

data3 = load(file, 'N_Node');
fields3 = fieldnames(data3.N_Node);
for k = 1:numel(fields3)
    fprintf('N_Node.%s = %s\n', fields3{k}, mat2str(data3.N_Node.(fields3{k})(:))');
end
fprintf('done\n');
