function probe_basepro()
% What geometry does BasePro.mat carry?  Field names, sizes, first rows only.
root = 'G:\研究生\SDITT-RW-FT-250728\SDITT-RW-FT-250728';
old = cd(root);
cleanup = onCleanup(@() cd(old));
S = load(fullfile(root, 'BasePro.mat'));
names = fieldnames(S);
fprintf('BasePro.mat variables: %s\n', strjoin(names', ', '));
for i = 1:numel(names)
    v = S.(names{i});
    fprintf('\n-- %s: %s %s\n', names{i}, class(v), mat2str(size(v)));
    if isstruct(v)
        fprintf('   fields: %s\n', strjoin(fieldnames(v)', ', '));
        if numel(v) >= 1
            f = fieldnames(v);
            for k = 1:min(3, numel(f))
                x = v(1).(f{k});
                if isnumeric(x) && ~isempty(x)
                    fprintf('   %s size %s  first: %s\n', f{k}, mat2str(size(x)), mat2str(x(1, :), 5));
                elseif ischar(x)
                    fprintf('   %s : %s\n', f{k}, x);
                end
            end
        end
    elseif isnumeric(v) && ~isempty(v)
        fprintf('   first rows:\n');
        rows = v(1:min(4, size(v, 1)), :);
        for r = 1:size(rows, 1)
            fprintf('     %s\n', mat2str(rows(r, :), 6));
        end
    end
end
% also peek at GeoPro_CrossSect and RailPro variable names
for other = {'GeoPro_CrossSect.mat', 'RailPro.mat'}
    T = load(fullfile(root, other{1}));
    fprintf('\n== %s variables: %s\n', other{1}, strjoin(fieldnames(T)', ', '));
end
end
